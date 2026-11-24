"""El almacén de claves (ADR-13): falla cerrado, huella en vez de secreto, reloj inyectable."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Callable, Iterable

from .clock import AuthClock, RealClock
from .errors import NO_AUTENTICADO, SIN_PERMISO, AuthError
from .models import (
    AUSENTE,
    DESCONOCIDA,
    MALFORMADA,
    REVOCADA,
    SECRETO_INCORRECTO,
    VENCIDA,
    AuthEvent,
    IssuedKey,
    KeyRecord,
    Principal,
)

KEY_ID_RE = re.compile(r"^[0-9a-f]{12}$")
MAX_PRESENTED = 200  # una clave emitida mide 56 caracteres; lo demás es basura o un intento de agotar
_COMODIN = "*"
# Contra esto se compara cuando el id no existe: mismo trabajo y misma respuesta
# para un id desconocido que para un secreto incorrecto.
_HUELLA_VACIA = "0" * 64

_Vista = tuple[Principal | None, str, str | None, str | None]


def verifier_of(secret: str) -> str:
    """Huella de un secreto: sha256 en hex.

    Sirve porque una clave son 256 bits aleatorios: no hay entropía baja que proteger.
    Con una contraseña humana esto estaría mal — por eso auth-base no contrata contraseñas.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _split(presented: str | None) -> tuple[str, str] | None:
    """Separa `<key_id>.<secreto>`; None si no tiene la forma de una clave emitida."""
    if presented is None or len(presented) > MAX_PRESENTED:
        return None
    key_id, sep, secret = presented.partition(".")
    if not sep or not KEY_ID_RE.match(key_id) or not secret:
        return None
    return key_id, secret


def _scopes(scopes: Iterable[str]) -> list[str]:
    limpios = sorted(set(scopes))
    if not limpios:
        raise ValueError("una clave sin permisos no sirve para nada")
    malos = [s for s in limpios if not s or s != s.strip() or any(ch.isspace() for ch in s) or _COMODIN in s]
    if malos:
        raise ValueError(f"permisos inválidos {malos}: explícitos, sin comodines ni espacios")
    return limpios


class KeyStore:
    """Las claves que un servicio acepta.

    Lo que no está aquí no entra. Y vacío no es una excepción: un store sin claves no
    deja entrar a nadie.
    """

    def __init__(self, *, clock: AuthClock | None = None, audit: Callable[[AuthEvent], None] | None = None) -> None:
        self._clock = clock if clock is not None else RealClock()
        self._audit = audit
        self._keys: dict[str, KeyRecord] = {}

    # -- emitir y quitar ---------------------------------------------------
    def issue(self, client: str, *, scopes: Iterable[str], ttl_seconds: float | None = None) -> IssuedKey:
        """Crea una clave para `client` con exactamente estos permisos."""
        permisos = _scopes(scopes)
        if not client or not client.strip():
            raise ValueError("falta el cliente de la clave")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds debe ser > 0 o None, recibido {ttl_seconds!r}")
        key_id = secrets.token_hex(6)  # 48 bits: identifica, no protege
        while key_id in self._keys:
            key_id = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)  # 256 bits: protege
        now = self._clock.now()
        expires_at = None if ttl_seconds is None else now + ttl_seconds
        self._keys[key_id] = KeyRecord(
            key_id=key_id,
            client=client,
            scopes=permisos,
            verifier=verifier_of(secret),
            created_at=now,
            expires_at=expires_at,
        )
        return IssuedKey(key=f"{key_id}.{secret}", key_id=key_id, client=client, scopes=permisos, expires_at=expires_at)

    def revoke(self, key_id: str) -> bool:
        """Quita una clave sin borrarla: el historial de accesos sigue teniendo sentido.

        True si la clave estaba viva y pasó a revocada; False si no existe o ya lo estaba.
        """
        record = self._keys.get(key_id)
        if record is None or record.revoked:
            return False
        self._keys[key_id] = record.model_copy(update={"revoked": True})
        return True

    # -- decidir -----------------------------------------------------------
    def _identify(self, presented: str | None) -> _Vista:
        """Autentica sin registrar: (principal o None, razón fina, cliente, key_id)."""
        partes = _split(presented)
        if partes is None:
            return None, AUSENTE if presented is None else MALFORMADA, None, None
        key_id, secret = partes
        record = self._keys.get(key_id)
        # Se calcula y se compara siempre, exista o no el id.
        coincide = hmac.compare_digest(record.verifier if record else _HUELLA_VACIA, verifier_of(secret))
        if record is None:
            return None, DESCONOCIDA, None, key_id
        if not coincide:
            return None, SECRETO_INCORRECTO, record.client, key_id
        # Desde aquí el secreto es correcto: el estado de la clave ya es del operador.
        if record.revoked:
            return None, REVOCADA, record.client, key_id
        if record.expires_at is not None and self._clock.now() >= record.expires_at:
            return None, VENCIDA, record.client, key_id
        return Principal(client=record.client, key_id=key_id, scopes=frozenset(record.scopes)), "", record.client, key_id

    def authenticate(self, presented: str | None) -> Principal | None:
        """¿Quién llama? None para todo lo que no sea una clave viva y correcta."""
        principal, reason, client, key_id = self._identify(presented)
        self._emit("ok" if principal else NO_AUTENTICADO, client=client, key_id=key_id, reason=reason)
        return principal

    def authorize(self, principal: Principal, scope: str) -> bool:
        """¿Puede esta clave hacer esto? Pertenencia exacta: sin comodines ni herencia."""
        return scope in principal.scopes

    def check(self, presented: str | None, scope: str) -> Principal:
        """Autentica y autoriza en un paso. Un evento por intento; falla cerrado con `AuthError`."""
        principal, reason, client, key_id = self._identify(presented)
        if principal is None:
            self._emit(NO_AUTENTICADO, client=client, key_id=key_id, scope=scope, reason=reason)
            raise AuthError(401, NO_AUTENTICADO, detail="credencial ausente o inválida")
        if not self.authorize(principal, scope):
            self._emit(SIN_PERMISO, client=principal.client, key_id=principal.key_id, scope=scope)
            raise AuthError(403, SIN_PERMISO, detail=f"la clave no tiene el permiso {scope!r}")
        self._emit("ok", client=principal.client, key_id=principal.key_id, scope=scope)
        return principal

    def _emit(self, outcome, *, client, key_id, scope=None, reason="") -> None:
        if self._audit is not None:
            self._audit(AuthEvent(at=self._clock.now(), outcome=outcome, client=client, key_id=key_id, scope=scope, reason=reason))

    # -- mirar y persistir -------------------------------------------------
    def get(self, key_id: str) -> KeyRecord | None:
        return self._keys.get(key_id)

    def list(self) -> list[KeyRecord]:
        return [self._keys[key_id] for key_id in sorted(self._keys)]

    def export(self) -> list[dict]:
        """Los registros sin ningún secreto: lo que el consumidor persiste."""
        return [record.model_dump(mode="json") for record in self.list()]

    @classmethod
    def load(cls, records: Iterable[dict], *, clock: AuthClock | None = None, audit: Callable[[AuthEvent], None] | None = None) -> KeyStore:
        store = cls(clock=clock, audit=audit)
        for record in records:
            parsed = KeyRecord.model_validate(record)
            store._keys[parsed.key_id] = parsed
        return store
