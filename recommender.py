import json
import os
import pandas as pd


def parse_pct(val_str):
    if pd.isna(val_str) or not isinstance(val_str, str) or val_str == "-":
        return 0.0
    clean_str = val_str.split(" ")[0].replace("%", "")
    try:
        return float(clean_str)
    except Exception:
        return 0.0


def generate_recommendations():
    print("Running quantitative recommendation engine with Trend Analysis...")

    profile_file = "outputs/risk_profile.json"
    risk_profile = "Moderate"
    if os.path.exists(profile_file):
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
                if isinstance(profile_data, dict):
                    risk_profile = profile_data.get(
                        "profile", profile_data.get("risk_profile", "Moderate")
                    )
                elif isinstance(profile_data, str):
                    risk_profile = profile_data
        except Exception as e:
            print(f"Error reading risk profile: {e}")

    csv_file = "outputs/portfolio_returns.csv"
    if not os.path.exists(csv_file):
        print("Performance CSV not found. Cannot generate recommendations.")
        return None

    df = pd.read_csv(csv_file, sep=";")
    month_cols = [c for c in df.columns if "/" in c]

    stocks_df = df[df["Type"] == "Stocks"].copy()
    watchlist_df = df[df["Type"] == "Watchlist"].copy()

    falling_knives = []
    rallies = []

    if len(month_cols) >= 3:
        last_3_months = month_cols[-3:]
        for _, row in stocks_df.iterrows():
            m1 = parse_pct(row[last_3_months[0]])
            m2 = parse_pct(row[last_3_months[1]])
            m3 = parse_pct(row[last_3_months[2]])
            if m1 < 0 and m2 < 0 and m3 < 0:
                falling_knives.append(row["Name"])
            elif m1 > 0 and m2 > 0 and m3 > 0:
                rallies.append(row["Name"])

    stocks_df["Last_Month_Float"] = stocks_df["Last Month Return"].apply(parse_pct)

    # Best / worst direct-stock names for last reported month (single axis for buy/sell copy)
    stocks_sorted_month = stocks_df.sort_values("Last_Month_Float", ascending=False)

    wl_sorted = None
    watchlist_best_name = None
    watchlist_best_lm = None
    if not watchlist_df.empty and "Last Month Return" in watchlist_df.columns:
        watchlist_df = watchlist_df.copy()
        watchlist_df["Last_Month_Float"] = watchlist_df["Last Month Return"].apply(parse_pct)
        wl_sorted = watchlist_df.sort_values("Last_Month_Float", ascending=False)
        watchlist_best_name = wl_sorted.iloc[0]["Name"]
        watchlist_best_lm = float(wl_sorted.iloc[0]["Last_Month_Float"])

    coverage_primary = None
    coverage_additional = []
    if wl_sorted is not None and len(wl_sorted) > 0:
        top = wl_sorted.iloc[0]
        coverage_primary = {
            "ticker": top["Name"],
            "last_month_pct": round(float(top["Last_Month_Float"]), 2),
        }
        for i in range(1, min(4, len(wl_sorted))):
            r = wl_sorted.iloc[i]
            coverage_additional.append(
                {
                    "ticker": r["Name"],
                    "last_month_pct": round(float(r["Last_Month_Float"]), 2),
                }
            )

    portfolio_weakest_name = None
    portfolio_weakest_lm = None
    if not stocks_df.empty and "Last Month Return" in stocks_df.columns:
        losers_lm = stocks_df.sort_values("Last_Month_Float", ascending=True)
        portfolio_weakest_name = losers_lm.iloc[0]["Name"]
        portfolio_weakest_lm = float(losers_lm.iloc[0]["Last_Month_Float"])

    rotation_eligible = False
    if (
        watchlist_best_name
        and portfolio_weakest_name
        and portfolio_weakest_lm is not None
        and watchlist_best_lm is not None
    ):
        weakest_is_falling = portfolio_weakest_name in falling_knives
        if (
            not weakest_is_falling
            and watchlist_best_lm > portfolio_weakest_lm + 0.5
            and portfolio_weakest_lm < 1.0
        ):
            rotation_eligible = True

    portfolio_issues = {
        "weakest_stock_last_month": None,
        "strongest_stock_last_month": None,
    }
    if portfolio_weakest_name is not None and portfolio_weakest_lm is not None:
        portfolio_issues["weakest_stock_last_month"] = {
            "name": portfolio_weakest_name,
            "pct": round(portfolio_weakest_lm, 2),
            "falling_knife_3m": portfolio_weakest_name in falling_knives,
        }
    if not stocks_sorted_month.empty:
        top = stocks_sorted_month.iloc[0]
        portfolio_issues["strongest_stock_last_month"] = {
            "name": top["Name"],
            "pct": round(float(top["Last_Month_Float"]), 2),
            "three_month_rally": top["Name"] in rallies,
        }

    strategy_applied = ""
    buy_rec = None
    sell_rec = None

    profile_lower = risk_profile.lower()

    if "aggressive" in profile_lower:
        strategy_applied = "Value Investing & Trend Analysis"

        losers = stocks_df.sort_values("Last_Month_Float", ascending=True)
        if not losers.empty:
            worst_stock = losers.iloc[0]["Name"]
            worst_return = losers.iloc[0]["Last_Month_Float"]

            if worst_stock in falling_knives:
                buy_rec = (
                    f"Atenção: {worst_stock} está em queda livre há 3 meses consecutivos. "
                    "Sugerimos aguardar um sinal de estabilização (fim do 'falling knife') antes de tentar comprar o desconto. "
                    "Aportar em fundos long-biased provisoriamente."
                )
            elif worst_return < -5.0:
                buy_rec = f"Aproveitar o desconto excessivo no mês de {worst_stock} para aumentar posição."
            else:
                buy_rec = "Aumentar exposição em Renda Variável via fundos multimercado long-biased."

        if not stocks_sorted_month.empty:
            best_stock = stocks_sorted_month.iloc[0]["Name"]
            if best_stock in rallies:
                sell_rec = (
                    f"{best_stock} apresentou rali de 3 meses seguidos. Momento ideal para realizar lucros parciais."
                )
            elif stocks_sorted_month.iloc[0]["Last_Month_Float"] > 10.0:
                sell_rec = f"Realizar lucros parciais em {best_stock} após forte alta mensal."
            else:
                sell_rec = "Reduzir parcela de Renda Fixa de baixo risco."

    elif "conservative" in profile_lower:
        strategy_applied = "Capital Protection & Stop Loss"

        losers_lm = stocks_df.sort_values("Last_Month_Float", ascending=True)
        if not losers_lm.empty:
            worst_lm_stock = losers_lm.iloc[0]["Name"]
            worst_lm_ret = float(losers_lm.iloc[0]["Last_Month_Float"])
            if worst_lm_stock in falling_knives:
                sell_rec = (
                    f"Acionar STRICT STOP-LOSS em {worst_lm_stock}, ativo acumula 3 meses seguidos de perdas "
                    "e contamina a carteira conservadora."
                )
            elif worst_lm_ret < -10.0:
                sell_rec = (
                    f"Reduzir exposição em {worst_lm_stock} após retorno muito negativo no último mês "
                    "na carteira de ações diretas."
                )
            else:
                sell_rec = "Reduzir posição global em Ações diretas."

        buy_rec = "Focar aportes em CDBs atrelados ao IPCA ou Fundos DI para proteção estrita do patrimônio."

    else:
        strategy_applied = "Tactical Volatility Rebalancing"

        losers_lm = stocks_df.sort_values("Last_Month_Float", ascending=True)
        if not stocks_sorted_month.empty and not losers_lm.empty:
            bottom_stock = losers_lm.iloc[0]["Name"]
            top_stock = stocks_sorted_month.iloc[0]["Name"]

            if bottom_stock in falling_knives:
                buy_rec = (
                    f"Manter cautela com {bottom_stock} que cai há 3 meses seguidos. "
                    "Focar os aportes de rebalanceamento em Fundos Multimercado ao invés de ações diretas em queda livre."
                )
            else:
                buy_rec = (
                    f"Manter aportes balanceados, reforçando taticamente no último mês o papel {bottom_stock} "
                    "(pior retorno mensal entre as ações diretas)."
                )

            if len(stocks_df) == 1:
                sell_rec = (
                    "Carteira com um único papel de RV: alinhar com o assessor aporte versus realização usando "
                    "apenas o último mês como referência quantitativa."
                )
            elif top_stock in rallies:
                sell_rec = (
                    f"Reduzir forte exposição em {top_stock} que engatou um rali de 3 meses de alta, rebalanceando a carteira."
                )
            else:
                sell_rec = (
                    f"Fazer rebalanceamento tático, reduzindo ligeiramente a exposição em {top_stock} "
                    "(melhor retorno mensal entre as ações diretas)."
                )

    recommendations = {
        "risk_profile_identified": risk_profile,
        "strategy_applied": strategy_applied,
        "buy_recommendation": buy_rec,
        "sell_recommendation": sell_rec,
        "portfolio_issues": portfolio_issues,
        "coverage_universe_last_month": {
            "primary": coverage_primary,
            "additional_discussion_options": coverage_additional,
        },
        "rotation_signal": {
            "eligible_laggard_vs_coverage_primary": rotation_eligible,
            "disclaimer": (
                "Ajustes de exposição exigem alinhamento com assessor, perfil, liquidez e preço-alvo; "
                "não é recomendação automática de compra ou venda."
            ),
        },
        "buy_sell_basis": {
            "stock_selection": "last_month_only",
            "note": (
                "Textos de compra e venda citam apenas o pior e o melhor desempenho no último mês reportado na tabela. "
                "As bandeiras falling_knife_3m e three_month_rally em portfolio_issues são contexto adicional, "
                "não um segundo eixo de ranqueamento."
            ),
        },
    }

    out_file = "outputs/recommendations.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(recommendations, f, ensure_ascii=False, indent=2)

    print(f"Recommendations saved at {out_file}")
    return out_file


if __name__ == "__main__":
    generate_recommendations()
