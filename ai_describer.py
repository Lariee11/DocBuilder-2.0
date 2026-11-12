"""
Geração da descrição detalhada da lógica com o Claude (Anthropic API).

Credenciais: o SDK lê ANTHROPIC_API_KEY (ou um perfil do `ant auth login`).
Modelo: variável de ambiente DOCBUILDER_CLAUDE_MODEL (padrão claude-opus-5-5).
Se a IA não estiver disponível, a API usa a descrição automática de sel_analyzer.
"""
import json
import os

SYSTEM_PROMPT = """Você é um engenheiro de proteção e automação de subestações que redige documentação técnica \
em português do Brasil para aplicações especiais em relés SEL (SELogic) e comunicação IEC 61850 GOOSE.

Você recebe:
- o contexto do projeto escrito pelo engenheiro responsável;
- as lógicas SELogic que mudaram entre o arquivo de backup (.rdb) e o arquivo novo, por relé;
- os ajustes de proteção/configuração que mudaram;
- a matriz GOOSE extraída do SCD (publicador, assinante, MAC, virtual bit, variável) e onde cada virtual bit é usado;
- uma lista de inconsistências detectadas automaticamente.

Escreva a "Descrição Detalhada da Lógica" do documento:
- Explique o funcionamento da solução como um todo (cadeia de sinais de ponta a ponta: origem do evento, \
mensagem GOOSE, virtual bit recebido, variável SELogic que processa e a ação final como trip, bloqueio ou alarme).
- Depois detalhe cada relé: o que cada lógica nova ou alterada faz, citando as variáveis e equações.
- Explique a supervisão de falha de comunicação GOOSE quando existir.
- Termine com uma seção "Pontos de atenção" que inclua as inconsistências recebidas e qualquer outra que você \
identifique nos dados (por exemplo trip condicionado a um grupo de ajuste, virtual bit sem assinatura, \
comentário que não condiz com a equação). Não omita nenhuma das inconsistências recebidas.
- Use somente as informações fornecidas. Quando algo não puder ser confirmado pelos dados, diga que precisa ser verificado.
- Use o contexto do engenheiro para dar sentido às lógicas (finalidade, equipamentos, filosofia), sem contradizer os dados.

Formato do texto (será convertido para LaTeX):
- Subtítulos em linhas que começam com "### ".
- Listas com linhas que começam com "- ".
- Nomes de variáveis, bits e equações entre crases, por exemplo `SV30T`.
- Parágrafos separados por linha em branco. Não use outra marcação Markdown (sem negrito, tabelas ou títulos # ou ##).

Também escreva, para cada linha da tabela de lógicas (identificada por "id"), uma descrição curta (uma ou duas frases) \
do que aquela lógica faz no contexto do projeto, para a coluna "Descrição" da tabela."""

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
