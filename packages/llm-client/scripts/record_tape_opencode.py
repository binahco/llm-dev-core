from pathlib import Path

from llm_client import CompletionRequest, LlmClient, ReplayProvider
from llm_client.providers.opencode_cli import OpenCodeCLI

MODEL = "opencode/big-pickle"
CASSETTES = Path(__file__).resolve().parents[1] / "tests" / "cassettes"

DIFF = """diff --git a/src/cli.py b/src/cli.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/src/cli.py
@@ -0,0 +1,3 @@
+def main():
+    print("hola")
"""

RENDERER = lambda prompt_id, prompt_version, variables: [
    {
        "role": "system",
        "content": "Generas mensajes de commit en formato Conventional Commits. Devuelve solo el mensaje, sin explicaciones.",
    },
    {
        "role": "user",
        "content": f"Diff:\n{variables['diff']}\n\nGenera el mensaje de commit.",
    },
]


def main() -> None:
    recorder = ReplayProvider(CASSETTES, record=True, inner=OpenCodeCLI(MODEL))
    client = LlmClient(
        recorder,
        consumer_repo="commit-cli",
        model_aliases={"fast": MODEL},
        retries=1,
        renderer=RENDERER,
    )
    result = client.complete(
        CompletionRequest(
            prompt_id="commit-message-generator",
            prompt_version="0.1.0",
            variables={"diff": DIFF},
            model_alias="fast",
            tags=["record", "seed-week2"],
        )
    )
    print(result.raw_text)


if __name__ == "__main__":
    main()