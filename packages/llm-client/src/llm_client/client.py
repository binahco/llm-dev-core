from __future__ import annotations

import json
import random
import time
from decimal import Decimal
from typing import Any, Callable

from .cache import ResponseCache, cache_key
from .models import CompletionRequest, CompletionResult, ValidationResult
from .pricing import cost_usd, resolve_model
from .provider import Provider, ProviderRequest
from .span import Span

Validator = Callable[[str, str | None], ValidationResult]
Renderer = Callable[[str, str, dict[str, Any]], list[dict]]
Emitter = Callable[[Span, CompletionResult | None], None]


class CostCapExceeded(Exception):
    def __init__(self, cost: Decimal, cap: Decimal, span_id: str) -> None:
        super().__init__(f"cost {cost} usd > cap {cap} usd")
        self.cost = cost
        self.cap = cap
        self.span_id = span_id


class StreamInterrupted(Exception):
    def __init__(self, partial_text: str) -> None:
        super().__init__("stream interrumpido tras entregar texto")
        self.partial_text = partial_text


def _noop_emitter(_span: Span, _result: CompletionResult | None) -> None:
    return None


class LlmClient:
    def __init__(
        self,
        provider: Provider,
        *,
        consumer_repo: str = "",
        model_aliases: dict[str, str] | None = None,
        retries: int = 3,
        repair_cap: int = 2,
        retry_base_ms: int = 300,
        retry_jitter_ms: int = 150,
        cache: ResponseCache | None = None,
        emitter: Emitter | None = None,
        cost_cap_usd: Decimal | None = None,
        cost_fn: Callable[[str, int | None, int | None], Decimal] = cost_usd,
        validator: Validator | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        self.provider = provider
        self.consumer_repo = consumer_repo
        self.model_aliases = model_aliases
        self.retries = retries
        self.repair_cap = repair_cap
        self.retry_base_ms = retry_base_ms
        self.retry_jitter_ms = retry_jitter_ms
        self.cache = cache
        self.emitter = emitter or _noop_emitter
        self.cost_cap_usd = cost_cap_usd
        self.cost_fn = cost_fn
        self.validator = validator or (lambda _text, _schema: ValidationResult(ok=True))
        self.renderer = renderer or self._default_renderer

    @staticmethod
    def _default_renderer(prompt_id: str, prompt_version: str, variables: dict[str, Any]) -> list[dict]:
        body = {"prompt_id": prompt_id, "prompt_version": prompt_version, "variables": variables}
        return [{"role": "user", "content": json.dumps(body, ensure_ascii=False)}]

    def _render(self, request: CompletionRequest, prompt_version: str, errors: list[str] | None = None) -> list[dict]:
        messages = self.renderer(request.prompt_id, prompt_version, request.variables)
        if errors:
            messages.append({"role": "assistant", "content": json.dumps({"validation_errors": errors})})
            messages.append({"role": "user", "content": "Corrige siguiendo el schema."})
        return messages

    def complete(self, request: CompletionRequest) -> CompletionResult:
        return self._execute(request, stream=False)

    def stream(self, request: CompletionRequest) -> CompletionResult:
        return self._execute(request, stream=True)

    @staticmethod
    def _collect_stream(stream) -> tuple[str, None]:
        parts: list[str] = []
        try:
            for chunk in stream:
                parts.append(chunk)
        except Exception as exc:
            raise StreamInterrupted("".join(parts)) from exc
        return "".join(parts), None

    def _execute(self, request: CompletionRequest, stream: bool) -> CompletionResult:
        start = time.perf_counter()
        prompt_version = request.prompt_version or "0.0.0"
        model = resolve_model(request.model_alias, self.model_aliases)
        span = Span(
            consumer_repo=self.consumer_repo,
            prompt_id=request.prompt_id,
            prompt_version=prompt_version,
            model_alias=request.model_alias,
            model=model,
            provider=self.provider.name,
        )

        if self.cache is not None:
            key = cache_key(request, prompt_version)
            hit = self.cache.get(key)
            if hit is not None:
                span.cache_hit = True
                span.call_skipped = True
                span.status = "skipped"
                span.latency_ms = 0
                self.emitter(span, hit)
                return hit

        attempts = 0
        repaired = 0
        last_error: Exception | None = None
        earlier_attempt_had_text = False
        final_path = "validation_failed"
        final_validation: ValidationResult | None = None
        final_text = ""
        final_cost = Decimal("0")
        final_usage = None

        while True:
            attempts += 1
            if attempts > 1 + self.retries + self.repair_cap:
                break

            errors = final_validation.errors if final_validation is not None and not final_validation.ok else None
            messages = self._render(request, prompt_version, errors)
            provider_request = ProviderRequest(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            try:
                if stream:
                    text, usage = self._collect_stream(self.provider.stream(provider_request))
                else:
                    response = self.provider.complete(provider_request)
                    text, usage = response.text, response.usage
            except Exception as exc:
                if isinstance(exc, StreamInterrupted) and exc.partial_text.strip():
                    earlier_attempt_had_text = True
                last_error = exc
                if attempts > 1 + self.retries:
                    break
                wait = self.retry_base_ms * (2 ** (attempts - 1)) + random.uniform(0, self.retry_jitter_ms)
                time.sleep(wait / 1000)
                continue

            had_text = bool(text.strip())
            validation = self.validator(text, request.response_schema)

            if validation.ok:
                span.latency_ms = int((time.perf_counter() - start) * 1000)
                span.tokens_input = usage.input_tokens if usage else None
                span.tokens_output = usage.output_tokens if usage else None
                span.cost_usd = self.cost_fn(model, span.tokens_input, span.tokens_output)
                span.retry_count = attempts - 1
                span.repaired_attempts = repaired
                span.status = "repaired" if repaired else "ok"
                span.retry_unnecessary = attempts > 1 and earlier_attempt_had_text
                if (
                    span.cost_usd is not None
                    and self.cost_cap_usd is not None
                    and span.cost_usd > self.cost_cap_usd
                ):
                    span.status = "blocked"
                    span.error_type = "cost_cap_exceeded"
                    self.emitter(span, None)
                    raise CostCapExceeded(span.cost_usd, self.cost_cap_usd, span.span_id)
                result = self._build_result(request, prompt_version, model, span, text, validation, usage)
                if self.cache is not None:
                    self.cache.put(key, result)
                self.emitter(span, result)
                return result

            earlier_attempt_had_text = earlier_attempt_had_text or had_text

            if repaired < self.repair_cap:
                repaired += 1
                final_validation = validation
                continue

            final_path = "validation_failed"
            final_validation = validation
            final_text = text
            final_usage = usage
            final_cost = self.cost_fn(model, usage.input_tokens if usage else None, usage.output_tokens if usage else None)
            break

        span.latency_ms = int((time.perf_counter() - start) * 1000)
        span.retry_count = attempts - 1
        span.repaired_attempts = repaired
        span.cost_usd = final_cost
        span.tokens_input = final_usage.input_tokens if final_usage else None
        span.tokens_output = final_usage.output_tokens if final_usage else None
        span.status = "failed"
        span.error_type = type(last_error).__name__ if last_error is not None else "validation"
        result = self._build_result(
            request,
            prompt_version,
            model,
            span,
            final_text,
            final_validation or ValidationResult(ok=False, errors=["sin respuesta"]),
            final_usage,
        )
        self.emitter(span, result)
        return result

    def _build_result(
        self,
        request: CompletionRequest,
        prompt_version: str,
        model: str,
        span: Span,
        text: str,
        validation: ValidationResult,
        usage: Any,
    ) -> CompletionResult:
        return CompletionResult(
            raw_text=text,
            parsed=getattr(validation, "parsed", None),
            validation=validation,
            usage=usage,
            cost_usd=span.cost_usd or Decimal("0"),
            latency_ms=span.latency_ms or 0,
            prompt_id=request.prompt_id,
            prompt_version=prompt_version,
            model_alias=request.model_alias,
            model=model,
            provider=self.provider.name,
            span_id=span.span_id,
        )