"""
Pipeline ETL — Estudantes da rede pública por nível de ensino, segundo as
Regiões Administrativas (RA) do Município do Rio de Janeiro (Censos 2000 e 2010).

Fonte primária: IPP / Armazém de Dados (Data.Rio), Tabela 892, a partir dos
Censos Demográficos do IBGE (2000 e 2010, dados da amostra).

Etapas
------
1. Extração ........ leitura das duas abas do .xls bruto, SEM alterar o arquivo.
2. Parsing ......... localização dinâmica do cabeçalho (3 linhas mescladas),
                     montagem dos nomes de coluna e recorte do bloco de dados.
3. Limpeza ......... normalização dos nomes das RA (espaços, erros de digitação),
                     separação do código romano, conversão de tipos e tratamento
                     dos marcadores especiais do IBGE:
                       "..."  -> NaN  (dado numérico não disponível, 2000)
                       "-"    -> 0    (zero absoluto, não resultante de arredondamento, 2010)
4. Harmonização .... os níveis de ensino de 2000 e 2010 têm desagregações
                     diferentes; criamos uma classificação comum (nível
                     harmonizado e etapa) e marcamos o que é comparável.
5. Validação ....... soma das parcelas x total publicado (por linha) e soma das
                     RA x total do município; resultados em relatorio_qualidade.json.
6. Persistência .... formato longo (tidy) em Parquet e CSV.gz + tabelas
                     analíticas derivadas.

Nenhuma etapa é destrutiva: cada valor carrega `valor_bruto` (texto original) e
`status_dado`, o que permite auditar qualquer conversão.

Uso:  python -m src.etl            (a partir da raiz do repositório)
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_BRUTO = RAIZ / "data" / "raw" / "tabela_892_estudantes_rede_publica_RA_2000_2010.xls"
PASTA_PROCESSADOS = RAIZ / "data" / "processed"

MARCADOR_NAO_DISPONIVEL = "..."   # nota da aba 2000
MARCADOR_ZERO_ABSOLUTO = "-"      # nota da aba 2010

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("etl")

# Correções de grafia observadas no arquivo bruto (rastreáveis)
CORRECOES_NOME_RA = {
    "IIha do Governador": "Ilha do Governador",
    "SantaTeresa": "Santa Teresa",
}

# Áreas de Planejamento (AP) — divisão oficial da Prefeitura do Rio
AREA_PLANEJAMENTO = {
    "AP1": ["Portuária", "Centro", "Rio Comprido", "São Cristóvão", "Paquetá", "Santa Teresa"],
    "AP2": ["Botafogo", "Copacabana", "Lagoa", "Tijuca", "Vila Isabel", "Rocinha"],
    "AP3": ["Ramos", "Penha", "Inhaúma", "Méier", "Irajá", "Madureira", "Ilha do Governador",
            "Anchieta", "Pavuna", "Jacarezinho", "Complexo do Alemão", "Maré", "Vigário Geral"],
    "AP4": ["Jacarepaguá", "Barra da Tijuca", "Cidade de Deus"],
    "AP5": ["Bangu", "Campo Grande", "Santa Cruz", "Guaratiba", "Realengo"],
}
RA_PARA_AP = {ra: ap for ap, lista in AREA_PLANEJAMENTO.items() for ra in lista}

# Harmonização dos níveis: chave = nome normalizado (sem acento, minúsculo)
# valor = (nivel_original_padronizado, nivel_harmonizado, etapa, comparavel_2000_2010)
HARMONIZACAO = [
    (r"^creche$",                                   "Creche", "Creche", "Educação Infantil", True),
    (r"^pre-escola$",                               "Pré-escola", "Pré-escola", "Educação Infantil", True),
    (r"^classe de alfabetizacao$",                  "Classe de alfabetização", "Classe de alfabetização", "Educação Infantil", True),
    (r"^alfabetizacao de adultos$",                 "Alfabetização de adultos", "Alfabetização de adultos", "Educação de Jovens e Adultos", True),
    (r"^ensino fundamental.*regular seriado$",      "Fundamental - regular seriado", "Fundamental regular", "Ensino Fundamental", True),
    (r"^ensino fundamental.*regular nao seriado$",  "Fundamental - regular não seriado", "Fundamental regular", "Ensino Fundamental", True),
    (r"^ensino fundamental.*regular$",              "Fundamental - regular", "Fundamental regular", "Ensino Fundamental", True),
    (r"^ensino fundamental.*supletivo$",            "Fundamental - supletivo", "Fundamental supletivo", "Educação de Jovens e Adultos", True),
    (r"^ensino medio.*regular seriado$",            "Médio - regular seriado", "Médio regular", "Ensino Médio", True),
    (r"^ensino medio.*regular nao seriado$",        "Médio - regular não seriado", "Médio regular", "Ensino Médio", True),
    (r"^ensino medio.*regular$",                    "Médio - regular", "Médio regular", "Ensino Médio", True),
    (r"^ensino medio.*supletivo$",                  "Médio - supletivo", "Médio supletivo", "Educação de Jovens e Adultos", True),
    (r"^pre-vestibular$",                           "Pré-vestibular", "Pré-vestibular", "Pré-vestibular", False),
    (r"^ensino superior.*graduacao$",               "Superior - graduação", "Superior graduação", "Ensino Superior", True),
    (r"^especializacao de nivel superior$",         "Especialização", "Especialização", "Ensino Superior", False),
    (r"^mestrado ou doutorado$",                    "Mestrado ou doutorado", "Mestrado/doutorado", "Ensino Superior", True),
    (r"^mestrado$",                                 "Mestrado", "Mestrado/doutorado", "Ensino Superior", True),
    (r"^doutorado$",                                "Doutorado", "Mestrado/doutorado", "Ensino Superior", True),
]

ORDEM_ETAPAS = ["Educação Infantil", "Ensino Fundamental", "Ensino Médio",
                "Educação de Jovens e Adultos", "Ensino Superior", "Pré-vestibular"]

ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50}


# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------
def normalizar_texto(texto: object) -> str:
    """Remove acentos, colapsa espaços e converte para minúsculas."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("1o.", "1o").replace("2o.", "2o")
    return re.sub(r"\s+", " ", s).strip().lower()


def romano_para_inteiro(romano: str) -> int:
    total, anterior = 0, 0
    for letra in reversed(romano.upper()):
        valor = ROMANOS[letra]
        total = total - valor if valor < anterior else total + valor
        anterior = max(anterior, valor)
    return total


def converter_valor(bruto: object) -> tuple[float, str]:
    """Converte uma célula em (valor numérico, status_dado) sem perder a origem."""
    if isinstance(bruto, (int, float, np.integer, np.floating)) and not pd.isna(bruto):
        return float(bruto), "observado"
    texto = str(bruto).strip() if bruto is not None else ""
    if texto == MARCADOR_NAO_DISPONIVEL:
        return np.nan, "nao_disponivel"
    if texto == MARCADOR_ZERO_ABSOLUTO:
        return 0.0, "zero_absoluto"
    if texto == "" or texto.lower() == "nan":
        return np.nan, "vazio"
    try:
        return float(texto.replace(".", "").replace(",", ".")), "observado"
    except ValueError:
        return np.nan, "invalido"


# ---------------------------------------------------------------------------
# 1-2. Extração e parsing
# ---------------------------------------------------------------------------
def extrair(caminho: Path = ARQUIVO_BRUTO) -> dict[int, pd.DataFrame]:
    """Lê todas as abas do arquivo bruto como texto/objeto (sem inferência)."""
    log.info("Lendo %s", caminho.name)
    abas = pd.read_excel(caminho, sheet_name=None, header=None, dtype=object, engine="calamine")
    return {int(nome): df for nome, df in abas.items()}


def localizar_cabecalho(bruto: pd.DataFrame) -> tuple[int, int, int]:
    """Retorna (linha do cabeçalho, linha inicial dos dados, linha final exclusiva)."""
    col0 = bruto[0].map(normalizar_texto)
    ini_cab = col0[col0.str.startswith("regioes administrativas")].index[0]
    ini_dados = col0[col0.str.startswith("rio de janeiro")].index[0]
    fim = ini_dados
    while fim < len(bruto) and normalizar_texto(bruto.iat[fim, 0]) != "":
        fim += 1
    return ini_cab, ini_dados, fim


def montar_colunas(bruto: pd.DataFrame, ini_cab: int) -> list[str]:
    """Combina as 3 linhas de cabeçalho mescladas em nomes únicos."""
    nivel = bruto.iloc[ini_cab + 1].ffill()          # mesclagem horizontal
    sub = bruto.iloc[ini_cab + 2]
    nomes = []
    for j in range(bruto.shape[1]):
        if j == 0:
            nomes.append("regiao_administrativa")
        elif j == 1:
            nomes.append("_vazia")
        elif j == 2:
            nomes.append("total_publicado")
        else:
            n = re.sub(r"\s+", " ", str(nivel.iat[j])).strip()
            s = sub.iat[j]
            nomes.append(f"{n} - {str(s).strip()}" if pd.notna(s) else n)
    return nomes


def classificar_nivel(nome_coluna: str) -> tuple[str, str, str, bool]:
    chave = normalizar_texto(nome_coluna)
    chave = re.sub(r" ou [12]o grau", "", chave).replace("superior- ", "superior - ")
    for padrao, original, harmonizado, etapa, comparavel in HARMONIZACAO:
        if re.search(padrao, chave):
            return original, harmonizado, etapa, comparavel
    raise ValueError(f"Nível de ensino não mapeado: {nome_coluna!r} -> {chave!r}")


def parse_aba(bruto: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Transforma uma aba bruta em formato longo (uma linha por RA x nível)."""
    ini_cab, ini_dados, fim = localizar_cabecalho(bruto)
    bloco = bruto.iloc[ini_dados:fim].copy()
    bloco.columns = montar_colunas(bruto, ini_cab)
    bloco = bloco.drop(columns="_vazia")
    log.info("Ano %s: %d linhas territoriais, %d colunas de nível",
             ano, len(bloco), bloco.shape[1] - 2)

    registros = []
    for _, linha in bloco.iterrows():
        territorio = parse_territorio(linha["regiao_administrativa"])
        total, status_total = converter_valor(linha["total_publicado"])
        for coluna in bloco.columns[2:]:
            original, harmonizado, etapa, comparavel = classificar_nivel(coluna)
            valor, status = converter_valor(linha[coluna])
            registros.append({
                "ano": ano, **territorio,
                "nivel_original": original, "nivel_harmonizado": harmonizado,
                "etapa": etapa, "comparavel_2000_2010": comparavel,
                "estudantes": valor, "status_dado": status,
                "valor_bruto": str(linha[coluna]).strip(),
                "total_publicado_ra": total,
            })
    return pd.DataFrame.from_records(registros)


def parse_territorio(rotulo: object) -> dict:
    texto = re.sub(r"\s+", " ", str(rotulo)).strip()
    if normalizar_texto(texto).startswith("rio de janeiro"):
        return {"nivel_territorial": "municipio", "ra_codigo": 0, "ra_romano": "",
                "ra_nome": "Município do Rio de Janeiro", "area_planejamento": "Total",
                "rotulo_bruto": str(rotulo)}
    m = re.match(r"^([IVXL]+)\s+(.+)$", texto)
    if not m:
        raise ValueError(f"Rótulo de RA fora do padrão: {rotulo!r}")
    romano, nome = m.group(1), m.group(2).strip()
    nome = CORRECOES_NOME_RA.get(nome, nome)
    return {"nivel_territorial": "regiao_administrativa",
            "ra_codigo": romano_para_inteiro(romano), "ra_romano": romano,
            "ra_nome": nome, "area_planejamento": RA_PARA_AP.get(nome, "Não mapeada"),
            "rotulo_bruto": str(rotulo)}


# ---------------------------------------------------------------------------
# 3-5. Transformação e validação
# ---------------------------------------------------------------------------
def transformar(abas: dict[int, pd.DataFrame]) -> pd.DataFrame:
    longo = pd.concat([parse_aba(df, ano) for ano, df in sorted(abas.items())], ignore_index=True)
    tipos = {"ano": "int16", "ra_codigo": "int16", "estudantes": "float64",
             "comparavel_2000_2010": "bool", "total_publicado_ra": "float64"}
    longo = longo.astype(tipos)
    for c in ["nivel_territorial", "area_planejamento", "etapa", "nivel_harmonizado",
              "nivel_original", "status_dado"]:
        longo[c] = longo[c].astype("category")
    nao_mapeadas = longo.loc[longo["area_planejamento"] == "Não mapeada", "ra_nome"].unique()
    if len(nao_mapeadas):
        raise ValueError(f"RA sem Área de Planejamento: {list(nao_mapeadas)}")
    return longo.sort_values(["ano", "ra_codigo", "etapa", "nivel_original"]).reset_index(drop=True)


def validar(longo: pd.DataFrame) -> dict:
    """Checagens de consistência; nada é corrigido aqui, apenas reportado."""
    rel: dict = {"arquivo_bruto": ARQUIVO_BRUTO.name, "anos": {}}
    for ano, g in longo.groupby("ano"):
        por_ra = g.groupby(["ra_codigo", "ra_nome"], observed=True).agg(
            soma_parcelas=("estudantes", "sum"), total_publicado=("total_publicado_ra", "first"))
        por_ra["dif_pct"] = 100 * (por_ra["soma_parcelas"] / por_ra["total_publicado"] - 1)
        ras = g[g["nivel_territorial"] == "regiao_administrativa"]
        mun = g[g["nivel_territorial"] == "municipio"]
        soma_ras = ras.drop_duplicates("ra_codigo")["total_publicado_ra"].sum()
        total_mun = mun["total_publicado_ra"].iloc[0]
        rel["anos"][int(ano)] = {
            "n_regioes_administrativas": int(ras["ra_codigo"].nunique()),
            "status_dado": g["status_dado"].value_counts().astype(int).to_dict(),
            "soma_totais_RA": round(float(soma_ras), 2),
            "total_municipio_publicado": round(float(total_mun), 2),
            "dif_RA_vs_municipio_pct": round(float(100 * (soma_ras / total_mun - 1)), 4),
            "max_abs_dif_parcelas_vs_total_pct": round(float(por_ra["dif_pct"].abs().max()), 4),
            "ra_com_maior_dif": por_ra["dif_pct"].abs().idxmax()[1],
            "celulas_nao_disponiveis": g.loc[g["status_dado"] == "nao_disponivel",
                                             ["ra_nome", "nivel_original"]].astype(str).values.tolist(),
        }
    ra_2000 = set(longo.query("ano == 2000 and ra_codigo > 0")["ra_nome"])
    ra_2010 = set(longo.query("ano == 2010 and ra_codigo > 0")["ra_nome"])
    rel["ra_somente_2000"] = sorted(ra_2000 - ra_2010)
    rel["ra_somente_2010"] = sorted(ra_2010 - ra_2000)
    for ano, info in rel["anos"].items():
        log.info("Validação %s: %d RA | dif. soma RA x município = %.3f%% | max dif parcelas x total = %.3f%%",
                 ano, info["n_regioes_administrativas"], info["dif_RA_vs_municipio_pct"],
                 info["max_abs_dif_parcelas_vs_total_pct"])
    return rel


# ---------------------------------------------------------------------------
# Tabelas analíticas derivadas (métricas)
# ---------------------------------------------------------------------------
def tabela_etapas(longo: pd.DataFrame, somente_comparaveis: bool = True) -> pd.DataFrame:
    """Estudantes por território x ano x etapa, com participação percentual."""
    base = longo[longo["comparavel_2000_2010"]] if somente_comparaveis else longo
    t = (base.groupby(["ano", "ra_codigo", "ra_nome", "area_planejamento", "etapa"], observed=True)
         ["estudantes"].sum(min_count=1).reset_index())
    t["total_territorio"] = t.groupby(["ano", "ra_codigo"])["estudantes"].transform("sum")
    t["participacao_pct"] = 100 * t["estudantes"] / t["total_territorio"]
    return t


def tabela_variacao_ra(longo: pd.DataFrame) -> pd.DataFrame:
    """Total comparável por RA em 2000 e 2010, variação absoluta, % e taxa anual (CAGR)."""
    base = longo[longo["comparavel_2000_2010"] & (longo["ra_codigo"] > 0)]
    w = (base.groupby(["ra_codigo", "ra_nome", "area_planejamento", "ano"], observed=True)
         ["estudantes"].sum(min_count=1).unstack("ano").reset_index())
    w.columns.name = None
    w = w.rename(columns={2000: "estudantes_2000", 2010: "estudantes_2010"})
    w["unidade_compatibilizada"] = False
    # Compatibilização territorial: a RA XXXI Vigário Geral não existe na tabela de 2000;
    # seus bairros (Cordovil, Jardim América, Parada de Lucas e Vigário Geral) eram
    # contabilizados na RA XI Penha. Para comparar 2000 x 2010 sem viés de redesenho
    # territorial, criamos uma unidade agregada adicional (as linhas originais são mantidas).
    pv = w[w["ra_nome"].isin(["Penha", "Vigário Geral"])]
    agregada = pd.DataFrame([{
        "ra_codigo": 1131, "ra_nome": "Penha + Vigário Geral", "area_planejamento": "AP3",
        "estudantes_2000": pv["estudantes_2000"].sum(min_count=1),
        "estudantes_2010": pv["estudantes_2010"].sum(min_count=1),
        "unidade_compatibilizada": True}])
    w = pd.concat([w, agregada], ignore_index=True)
    w["variacao_abs"] = w["estudantes_2010"] - w["estudantes_2000"]
    w["variacao_pct"] = 100 * (w["estudantes_2010"] / w["estudantes_2000"] - 1)
    w["taxa_anual_pct"] = 100 * ((w["estudantes_2010"] / w["estudantes_2000"]) ** (1 / 10) - 1)
    originais = ~w["unidade_compatibilizada"]
    for ano in (2000, 2010):
        total = w.loc[originais, f"estudantes_{ano}"].sum()
        w[f"participacao_municipio_{ano}_pct"] = 100 * w[f"estudantes_{ano}"] / total
    return w.sort_values("ra_codigo").reset_index(drop=True)


def indicador_superior(longo: pd.DataFrame) -> pd.DataFrame:
    """% de estudantes em graduação + mestrado/doutorado no total comparável da RA."""
    et = tabela_etapas(longo)
    sup = et[et["etapa"] == "Ensino Superior"][["ano", "ra_codigo", "ra_nome", "area_planejamento",
                                                 "estudantes", "participacao_pct"]]
    sup = sup.rename(columns={"estudantes": "estudantes_superior",
                              "participacao_pct": "pct_superior"})
    return sup.reset_index(drop=True)


def gini(valores: np.ndarray) -> float:
    """Coeficiente de Gini (0 = distribuição igual, 1 = concentração total)."""
    x = np.sort(np.asarray(valores, dtype=float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


# ---------------------------------------------------------------------------
# 6. Persistência
# ---------------------------------------------------------------------------
def salvar(df: pd.DataFrame, nome: str) -> None:
    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PASTA_PROCESSADOS / f"{nome}.parquet", index=False)
    df.to_csv(PASTA_PROCESSADOS / f"{nome}.csv.gz", index=False, compression="gzip",
              encoding="utf-8")
    log.info("Salvo: data/processed/%s.{parquet,csv.gz} (%d linhas)", nome, len(df))


def executar() -> pd.DataFrame:
    abas = extrair()
    longo = transformar(abas)
    relatorio = validar(longo)
    salvar(longo, "estudantes_ra_nivel_longo")
    salvar(tabela_etapas(longo), "estudantes_ra_etapa")
    salvar(tabela_variacao_ra(longo), "variacao_ra_2000_2010")
    salvar(indicador_superior(longo), "indicador_ensino_superior_ra")
    with open(PASTA_PROCESSADOS / "relatorio_qualidade.json", "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)
    log.info("Pipeline concluído.")
    return longo


if __name__ == "__main__":
    executar()
