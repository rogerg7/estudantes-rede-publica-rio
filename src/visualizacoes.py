"""
Geração das figuras do artigo (estáticas em PNG via Matplotlib e interativas
em HTML via Plotly). Lê exclusivamente os dados processados por `src.etl`.

Uso:  python -m src.visualizacoes      (a partir da raiz do repositório)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.etl import ORDEM_ETAPAS, PASTA_PROCESSADOS, RAIZ, gini

PASTA_FIGURAS = RAIZ / "docs" / "assets"
PASTA_INTERATIVOS = PASTA_FIGURAS / "interativos"

# Paleta (validada para daltonismo — ver README) ------------------------------
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SEC = "#52514e"
GRADE = "#e6e5e1"
COR_2000 = "#86b6ef"      # azul claro (passo 250) — ano base
COR_2010 = "#2a78d6"      # azul (passo 450) — ano final
COR_POSITIVO = "#2a78d6"  # divergente: crescimento
COR_NEGATIVO = "#e34948"  # divergente: retração
COR_NEUTRA = "#b9b8b3"
CORES_ETAPA = {
    "Educação Infantil": "#2a78d6",
    "Ensino Fundamental": "#eb6834",
    "Ensino Médio": "#1baf7a",
    "Educação de Jovens e Adultos": "#eda100",
    "Ensino Superior": "#e87ba4",
}

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 200, "font.family": "DejaVu Sans", "font.size": 10,
    "axes.facecolor": SUPERFICIE, "figure.facecolor": SUPERFICIE, "axes.edgecolor": GRADE,
    "axes.labelcolor": TEXTO_SEC, "xtick.color": TEXTO_SEC, "ytick.color": TEXTO_SEC,
    "text.color": TEXTO, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
    "axes.titlesize": 12, "axes.titlelocation": "left",
})

FMT_MILHAR = mticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", "."))


def fmt_br(x: float, casas: int = 0) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def layout_plotly(fig: go.Figure, titulo: str, altura: int = 520) -> go.Figure:
    fig.update_layout(
        title=dict(text=titulo, x=0, xanchor="left", font=dict(size=15, color=TEXTO)),
        paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE, height=altura,
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", color=TEXTO_SEC, size=12),
        margin=dict(l=10, r=20, t=80, b=40), hoverlabel=dict(bgcolor="white", font_size=12),
        separators=",.",
    )
    fig.update_xaxes(gridcolor=GRADE, zerolinecolor="#c9c8c3", linecolor=GRADE)
    fig.update_yaxes(gridcolor=GRADE, zerolinecolor="#c9c8c3", linecolor=GRADE)
    return fig


def salvar_plotly(fig: go.Figure, nome: str) -> Path:
    PASTA_INTERATIVOS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_INTERATIVOS / f"{nome}.html"
    # plotly.min.js é gravado uma única vez na pasta: funciona offline e no GitHub Pages
    fig.write_html(destino, include_plotlyjs="directory", full_html=True,
                   config={"displaylogo": False, "responsive": True, "locale": "pt-BR"})
    return destino


def carregar() -> dict[str, pd.DataFrame]:
    return {n: pd.read_parquet(PASTA_PROCESSADOS / f"{n}.parquet") for n in
            ["estudantes_ra_nivel_longo", "estudantes_ra_etapa",
             "variacao_ra_2000_2010", "indicador_ensino_superior_ra"]}


# ---------------------------------------------------------------------------
# RQ1 — composição por etapa
# ---------------------------------------------------------------------------
def fig1_etapas_municipio(etapa: pd.DataFrame) -> Path:
    m = (etapa[etapa["ra_codigo"] == 0].pivot(index="etapa", columns="ano", values="estudantes")
         .reindex([e for e in ORDEM_ETAPAS if e in CORES_ETAPA]))
    m["var"] = 100 * (m[2010] / m[2000] - 1)
    m = m.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(m))
    h = 0.36
    ax.barh(y + h / 2, m[2000], height=h, color=COR_2000, label="2000")
    ax.barh(y - h / 2, m[2010], height=h, color=COR_2010, label="2010")
    for i, (_, r) in enumerate(m.iterrows()):
        sinal = "+" if r["var"] >= 0 else "−"
        ax.text(max(r[2000], r[2010]) + 9000, i, f"{sinal}{fmt_br(abs(r['var']), 1)}%",
                va="center", fontsize=10, fontweight="bold", color=TEXTO)
    ax.set_yticks(y, m.index)
    ax.xaxis.set_major_formatter(FMT_MILHAR)
    ax.set_xlim(0, m[[2000, 2010]].max().max() * 1.17)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Número de estudantes da rede pública")
    ax.set_title("Estudantes da rede pública por etapa de ensino — Rio de Janeiro", loc="left", x=-0.28)
    ax.legend(loc="lower right", frameon=False, title="Ano (rótulo = variação 2000→2010)",
              title_fontsize=9)
    fig.text(0.01, 0.01, "Fonte: IBGE, Censos 2000 e 2010 (amostra), via IPP/Data.Rio — Tabela 892. "
             "Apenas níveis comparáveis.", fontsize=8, color=TEXTO_SEC)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    destino = PASTA_FIGURAS / "fig1_etapas_municipio.png"
    fig.savefig(destino)
    plt.close(fig)
    return destino


def fig2_composicao_ap(etapa: pd.DataFrame) -> Path:
    e = etapa[etapa["ra_codigo"] > 0]
    t = e.groupby(["area_planejamento", "ano", "etapa"], observed=True)["estudantes"].sum().reset_index()
    t["pct"] = 100 * t["estudantes"] / t.groupby(["area_planejamento", "ano"], observed=True)["estudantes"].transform("sum")
    t["rotulo"] = t["area_planejamento"].astype(str) + " · " + t["ano"].astype(str)
    ordem = [f"AP{i} · {a}" for i in range(1, 6) for a in (2000, 2010)]
    fig = go.Figure()
    for et, cor in CORES_ETAPA.items():
        d = t[t["etapa"] == et].set_index("rotulo").reindex(ordem)
        fig.add_bar(y=ordem, x=d["pct"], name=et, orientation="h", marker=dict(color=cor, line=dict(color=SUPERFICIE, width=2)),
                    customdata=np.c_[d["estudantes"].round(0)],
                    hovertemplate="<b>%{y}</b><br>" + et + ": %{x:.1f}%<br>Estudantes: %{customdata[0]:,.0f}<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.35, legend=dict(orientation="h", y=-0.12, x=0, traceorder="normal"))
    fig.update_xaxes(title="% dos estudantes da rede pública", range=[0, 100], ticksuffix="%")
    fig.update_yaxes(autorange="reversed")
    layout_plotly(fig, "Composição por etapa de ensino<br><sup>segundo a Área de Planejamento — 2000 e 2010</sup>", 560)
    return salvar_plotly(fig, "fig2_composicao_ap")


# ---------------------------------------------------------------------------
# RQ2 — distribuição territorial e variação
# ---------------------------------------------------------------------------
def fig3_variacao_ra(variacao: pd.DataFrame) -> Path:
    v = variacao[~variacao["ra_nome"].isin(["Penha", "Vigário Geral"])].dropna(subset=["variacao_pct"])
    v = v.sort_values("variacao_pct")
    nomes = [n + " *" if c else n for n, c in zip(v["ra_nome"], v["unidade_compatibilizada"])]
    cores = [COR_POSITIVO if x >= 0 else COR_NEGATIVO for x in v["variacao_pct"]]
    fig = go.Figure(go.Bar(
        x=v["variacao_pct"], y=nomes, orientation="h", marker=dict(color=cores),
        customdata=np.c_[v["area_planejamento"].astype(str), v["estudantes_2000"], v["estudantes_2010"],
                         v["variacao_abs"], v["taxa_anual_pct"]],
        hovertemplate=("<b>%{y}</b> (%{customdata[0]})<br>2000: %{customdata[1]:,.0f}<br>"
                       "2010: %{customdata[2]:,.0f}<br>Variação: %{customdata[3]:+,.0f} (%{x:+.1f}%)"
                       "<br>Taxa anual: %{customdata[4]:+.2f}% a.a.<extra></extra>"),
        text=[f"{x:+.1f}%".replace(".", ",") for x in v["variacao_pct"]], textposition="outside",
        textfont=dict(color=TEXTO, size=11), cliponaxis=False))
    originais = variacao[~variacao["unidade_compatibilizada"]]
    var_municipio = 100 * (originais["estudantes_2010"].sum() / originais["estudantes_2000"].sum() - 1)
    fig.add_vline(x=float(var_municipio),
                  line=dict(color=TEXTO_SEC, width=1, dash="dot"),
                  annotation_text="média do município", annotation_position="top")
    fig.update_xaxes(title="Variação 2000→2010 (%)", ticksuffix="%",
                     range=[v["variacao_pct"].min() - 12, v["variacao_pct"].max() + 15])
    fig.update_layout(bargap=0.3, showlegend=False)
    layout_plotly(fig, "Variação de estudantes, 2000→2010<br><sup>por Região Administrativa (* território compatibilizado)</sup>", 820)
    return salvar_plotly(fig, "fig3_variacao_ra")


def fig4_lorenz(variacao: pd.DataFrame) -> Path:
    v = variacao[~variacao["unidade_compatibilizada"]]
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    ax.plot([0, 100], [0, 100], color=COR_NEUTRA, lw=1.2, label="Igualdade perfeita")
    for ano, cor in ((2000, COR_2000), (2010, COR_2010)):
        x = np.sort(v[f"estudantes_{ano}"].dropna().values)
        ac = np.r_[0, np.cumsum(x) / x.sum() * 100]
        pr = np.linspace(0, 100, len(ac))
        ax.plot(pr, ac, color=cor, lw=2.2, marker="o", ms=3.5,
                label=f"{ano}  (Gini = {fmt_br(gini(x), 3)}; n = {len(x)} RA)")
    ax.set_xlabel("% acumulado de Regiões Administrativas (da menor para a maior)")
    ax.set_ylabel("% acumulado de estudantes da rede pública")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_title("Curva de Lorenz — estudantes por RA", loc="left", x=-0.12)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    fig.tight_layout()
    destino = PASTA_FIGURAS / "fig4_lorenz_concentracao.png"
    fig.savefig(destino)
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# RQ3 — desigualdade territorial no ensino superior público
# ---------------------------------------------------------------------------
def fig5_halteres_superior(superior: pd.DataFrame) -> Path:
    p = (superior[superior["ra_codigo"] > 0].pivot_table(index=["ra_nome", "area_planejamento"],
         columns="ano", values="pct_superior", observed=True).reset_index())
    p = p.sort_values([2010], ascending=True)
    fig = go.Figure()
    for _, r in p.iterrows():
        if pd.notna(r[2000]):
            fig.add_trace(go.Scatter(x=[r[2000], r[2010]], y=[r["ra_nome"]] * 2, mode="lines",
                                     line=dict(color="#d3d2cd", width=3), hoverinfo="skip", showlegend=False))
    for ano, cor in ((2000, COR_2000), (2010, COR_2010)):
        fig.add_trace(go.Scatter(
            x=p[ano], y=p["ra_nome"], mode="markers", name=str(ano),
            marker=dict(color=cor, size=11, line=dict(color=SUPERFICIE, width=2)),
            customdata=np.c_[p["area_planejamento"].astype(str), p[2000], p[2010]],
            hovertemplate=("<b>%{y}</b> (%{customdata[0]})<br>2000: %{customdata[1]:.2f}%<br>"
                           "2010: %{customdata[2]:.2f}%<extra></extra>")))
    mun = superior[superior["ra_codigo"] == 0].set_index("ano")["pct_superior"]
    fig.add_vline(x=float(mun[2010]), line=dict(color=TEXTO_SEC, width=1, dash="dot"),
                  annotation_text=f"município 2010: {fmt_br(mun[2010], 1)}%", annotation_position="top")
    fig.update_xaxes(title="% dos estudantes da rede pública da RA",
                     ticksuffix="%", rangemode="tozero")
    fig.update_yaxes(categoryorder="array", categoryarray=list(p["ra_nome"]))
    fig.update_layout(legend=dict(orientation="h", y=-0.06, x=0, title="Ano"))
    layout_plotly(fig, "Peso do ensino superior na rede pública<br><sup>% de estudantes em graduação e mestrado/doutorado, por RA</sup>", 860)
    return salvar_plotly(fig, "fig5_superior_ra")


def fig6_dispersao_superior(superior: pd.DataFrame) -> Path:
    p = (superior[superior["ra_codigo"] > 0].pivot(index="ra_nome", columns="ano", values="pct_superior")
         .dropna())
    fig, ax = plt.subplots(figsize=(7.2, 6))
    lim = p.max().max() * 1.08
    ax.plot([0, lim], [0, lim], color=COR_NEUTRA, lw=1.2)
    ax.text(lim * 0.86, lim * 0.70, "y = x\n(sem mudança)", color=TEXTO_SEC, fontsize=8, ha="center")
    ax.scatter(p[2000], p[2010], s=46, color=COR_2010, edgecolor=SUPERFICIE, linewidth=1.5, zorder=3)
    destaque = ["Botafogo", "Copacabana", "Lagoa", "Tijuca", "Vila Isabel", "Centro", "Barra da Tijuca",
                "Complexo do Alemão", "Penha", "Paquetá"]
    desloc = {"Tijuca": (6, -4), "Lagoa": (-38, 4), "Vila Isabel": (6, -9), "Centro": (-40, 3),
              "Barra da Tijuca": (6, -9), "Penha": (6, 0), "Paquetá": (8, -3),
              "Complexo do Alemão": (95, 20)}
    for n in destaque:
        if n in p.index:
            dx, dy = desloc.get(n, (6, 3))
            ax.annotate(n, (p.loc[n, 2000], p.loc[n, 2010]), xytext=(dx, dy),
                        textcoords="offset points", fontsize=8.5, color=TEXTO,
                        arrowprops=dict(arrowstyle="-", color=TEXTO_SEC, lw=0.6) if n == "Complexo do Alemão" else None)
    from scipy.stats import spearmanr
    rho = spearmanr(p[2000], p[2010]).statistic
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_xlabel("% de estudantes no ensino superior — 2000")
    ax.set_ylabel("% de estudantes no ensino superior — 2010")
    ax.set_title(f"Persistência da hierarquia territorial (Spearman ρ = {fmt_br(rho, 2)})")
    fig.tight_layout()
    destino = PASTA_FIGURAS / "fig6_dispersao_superior.png"
    fig.savefig(destino)
    plt.close(fig)
    return destino


def gerar_todas() -> list[Path]:
    PASTA_FIGURAS.mkdir(parents=True, exist_ok=True)
    d = carregar()
    return [
        fig1_etapas_municipio(d["estudantes_ra_etapa"]),
        fig2_composicao_ap(d["estudantes_ra_etapa"]),
        fig3_variacao_ra(d["variacao_ra_2000_2010"]),
        fig4_lorenz(d["variacao_ra_2000_2010"]),
        fig5_halteres_superior(d["indicador_ensino_superior_ra"]),
        fig6_dispersao_superior(d["indicador_ensino_superior_ra"]),
    ]


if __name__ == "__main__":
    for caminho in gerar_todas():
        print("Gerado:", caminho.relative_to(RAIZ))
