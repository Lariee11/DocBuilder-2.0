"""
Geração da descrição detalhada da lógica com o Claude (Anthropic API).

Credenciais: o SDK lê ANTHROPIC_API_KEY (ou um perfil do `ant auth login`).
Modelo: variável de ambiente DOCBUILDER_CLAUDE_MODEL (padrão claude-opus-5-5).
Se a IA não estiver disponível, a API usa a descrição automática de sel_analyzer.
"""
import json
import os

SYSTEM_PROMPT = """Você é um engenheiro de proteção e automação de subestações que redige documentação técnica \
em português do Brasil para aplicações especiais em relés de proteção e comunicação IEC 61850 GOOSE.

Você recebe o contexto do projeto escrito pelo engenheiro responsável e os dados extraídos dos arquivos: \
lógicas que mudaram entre o backup e o arquivo novo, ajustes de proteção alterados, matriz GOOSE e onde cada sinal \
recebido é usado. Esses dados servem para você entender o que foi feito; o leitor do documento já terá as tabelas \
com as lógicas e os sinais GOOSE.

Escreva a "Descrição Detalhada da Lógica": um texto corrido que explique o que foi realizado e por que, \
do ponto de vista do sistema elétrico.
- Explique a finalidade de cada alteração em termos de proteção e operação: eliminação rápida de faltas, \
isolamento do equipamento defeituoso, seletividade e coordenação, bloqueio de religamento sobre defeito, \
confiabilidade da comunicação, adequação a condições operativas, segurança da operação.
- Refira-se aos equipamentos pelos nomes (por exemplo "o relé do disjuntor 52-2", "a proteção do transformador T1"). \
Não cite equações, variáveis internas, nomes de bits, endereços, MACs, nomes de ajustes ou operadores lógicos \
(nada como SV30T, VB001, TR, SG1, AND/OR).
- Use o contexto do engenheiro como fonte principal do "por quê". Quando o contexto não disser o motivo, \
deduza-o apenas dos fundamentos de proteção e só se for evidente pelos dados; não invente fatos.
- Seja direto: de 2 a 4 parágrafos curtos, no máximo cerca de 250 palavras. Sem subtítulos, sem listas, \
sem introduções genéricas e sem repetir o contexto literalmente.
- Não inclua a lista de inconsistências; ela é exibida separadamente.
- Texto simples em parágrafos separados por linha em branco, sem nenhuma marcação.

Escreva também, para cada linha da tabela de lógicas (identificada por "id"), uma descrição curta (uma frase) \
da finalidade daquela lógica, para a coluna "Descrição" da tabela."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "descricao_detalhada": {"type": "string"},
        "descricoes_logicas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "descricao": {"type": "string"}},
                "required": ["id", "descricao"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["descricao_detalhada", "descricoes_logicas"],
    "additionalProperties": False,
}


class AIUnavailable(Exception):
    """A descrição por IA não pôde ser gerada; a mensagem explica o motivo."""


def _build_payload(analysis: dict, context: str) -> str:
    logic = [{"id": i, "rele": c["relay"], "variavel": c["variable"], "onde": c["scope"], "status": c["status"],
              "equacao_anterior": c["old_expr"], "equacao_nova": c["new_expr"], "comentario": c["comment"]}
             for i, c in enumerate(analysis["logic_changes"])]
    goose = [{"publicador": e["pub"], "mensagem": e["cb"], "mac": e["mac"], "appid": e["appid"],
              "assinante": e["sub"] or None, "virtual_bit": e["vb"] or None, "variavel": e["variable"],
              "usado_em": analysis["vb_usage"].get(f"{e['sub']}|{e['vb']}", [])}
             for e in analysis["goose_entries"]]
    data = {
        "reles": analysis["relays"],
        "ieds_scd": analysis["ieds"],
        "logicas_alteradas": logic,
        "ajustes_alterados": analysis["settings_changes"],
        "matriz_goose": goose,
        "goose_diferencas_backup": {
            k: [{"publicador": e["pub"], "assinante": e["sub"], "virtual_bit": e["vb"], "variavel": e["variable"]}
                for e in v]
            for k, v in (analysis.get("goose_diff") or {}).items()
        },
        "inconsistencias_detectadas": analysis["warnings"],
    }
    return (f"<contexto_do_projeto>\n{context.strip() or '(não informado)'}\n</contexto_do_projeto>\n\n"
            f"<dados_extraidos>\n{json.dumps(data, ensure_ascii=False, indent=1)}\n</dados_extraidos>")


def generate_description(analysis: dict, context: str) -> dict:
    """Retorna {"descricao_detalhada": str, "descricoes_logicas": {id: str}, "modelo": str}."""
    try:
        import anthropic
    except ImportError as exc:
        raise AIUnavailable("o pacote 'anthropic' não está instalado (pip install anthropic)") from exc

    model = os.environ.get("DOCBUILDER_CLAUDE_MODEL", "claude-opus-5-5")
    try:
        client = anthropic.Anthropic()
        with client.beta.messages.stream(
            model=model,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_payload(analysis, context)}],
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise AIUnavailable("credencial da Anthropic inválida ou ausente (defina ANTHROPIC_API_KEY)") from exc
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
        raise AIUnavailable("o modelo recusou gerar a descrição")
    if response.stop_reason == "max_tokens":
        raise AIUnavailable("a resposta da IA foi cortada por excesso de tamanho")

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIUnavailable("a resposta da IA não veio em JSON válido") from exc
    return {
        "descricao_detalhada": data.get("descricao_detalhada", "").strip(),
        "descricoes_logicas": {int(d["id"]): d["descricao"].strip() for d in data.get("descricoes_logicas", [])},
        "modelo": response.model,
    }
