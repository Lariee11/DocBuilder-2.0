"""
Revisão automática da Descrição Detalhada com o Claude (Anthropic API).

Credenciais: o SDK lê ANTHROPIC_API_KEY (ou um perfil do `ant auth login`).
Modelo: variável de ambiente DOCBUILDER_CLAUDE_MODEL (padrão claude-opus-5-5).
"""
import json
import os

SYSTEM_PROMPT = """Você revisa textos de documentação técnica de proteção, automação e controle de subestações \
(relés de proteção, lógicas, comunicação IEC 61850/GOOSE, DNP3, SCADA), em português do Brasil.

Revise o texto recebido:
- Corrija gramática, ortografia, concordância, pontuação e acentuação.
- Deixe a redação mais técnica e objetiva, com a terminologia usual da área \
(por exemplo "disparo", "abertura do disjuntor", "seletividade", "grupo de ajustes", "supervisório").
- Mantenha exatamente o mesmo conteúdo e sentido: não acrescente fatos, motivos, equipamentos ou valores \
que não estejam no texto, não remova informações e não mude conclusões.
- Mantenha nomes de equipamentos, códigos, variáveis e números exatamente como estão.
- Mantenha o tamanho próximo ao original; não acrescente introdução nem conclusão.
- Preserve a estrutura de parágrafos e qualquer marcação existente (linhas iniciadas por "### " ou "- ", \
trechos entre crases). Não acrescente marcações novas.
- Se o texto já estiver correto, devolva-o com o mínimo de alterações."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"texto_revisado": {"type": "string"}},
    "required": ["texto_revisado"],
    "additionalProperties": False,
}


class AIUnavailable(Exception):
    """O texto não pôde ser revisado; a mensagem explica o motivo."""


def improve_text(texto: str) -> dict:
    """Retorna {"texto": str, "modelo": str}."""
    try:
        import anthropic
    except ImportError as exc:
        raise AIUnavailable("o pacote 'anthropic' não está instalado (pip install anthropic)") from exc

    model = os.environ.get("DOCBUILDER_CLAUDE_MODEL", "claude-opus-5-5")
    try:
        client = anthropic.Anthropic()
        with client.beta.messages.stream(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"<texto>\n{texto}\n</texto>"}],
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise AIUnavailable("credencial da Anthropic inválida (verifique ANTHROPIC_API_KEY)") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AIUnavailable(f"sem permissão para usar o modelo {model}") from exc
    except anthropic.RateLimitError as exc:
        raise AIUnavailable("limite de requisições da API atingido; tente novamente em instantes") from exc
    except anthropic.APIStatusError as exc:
        raise AIUnavailable(f"erro da API ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AIUnavailable("sem conexão com a API da Anthropic") from exc
    except TypeError as exc:
        # Cliente sem credencial configurada
        raise AIUnavailable("credencial da Anthropic não configurada (defina a variável ANTHROPIC_API_KEY "
                            "antes de iniciar a API)") from exc

    if response.stop_reason == "refusal":
        raise AIUnavailable("o modelo recusou revisar o texto")
    if response.stop_reason == "max_tokens":
        raise AIUnavailable("o texto é longo demais para ser revisado de uma vez")

    raw = next((b.text for b in response.content if b.type == "text"), "")
    try:
        revisado = json.loads(raw)["texto_revisado"].strip()
    except (json.JSONDecodeError, KeyError) as exc:
        raise AIUnavailable("a resposta da IA veio em formato inesperado") from exc
    return {"texto": revisado, "modelo": response.model}
