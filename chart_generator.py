import matplotlib.pyplot as plt
import pandas as pd
import os


def _skip_chart_top_bottom(name) -> bool:
    """Holdings excluded from top/bottom performer lines (e.g. missing last-month series)."""
    if pd.isna(name):
        return False
    u = str(name).upper()
    return "CONSIGNADO" in u and "C6" in u


def generate_performance_chart(chart_data):
    if not chart_data:
        print("No chart data available.")
        return None
        
    print("Generating performance chart...")
    df = chart_data['df']
    sorted_months = chart_data['sorted_months']
    cdi_returns = chart_data['cdi_returns']
    
    # Identify candidates for plotting (portfolio holdings only — not aggregate or watchlist)
    assets_df = df[df["Type"].isin(["Stocks", "Funds", "Fixed Revenue"])].copy()
    assets_df = assets_df[~assets_df["Name"].map(_skip_chart_top_bottom)]

    # Sort by Last Month Return to find Top 2 and Bottom 2 of the last month
    # Ensure Last Month Return is float (it was before formatting)
    assets_df = assets_df.sort_values(by='Last Month Return', ascending=False)
    
    top_2 = assets_df.head(2)
    bottom_2 = assets_df.tail(2)
    portfolio = df[df['Type'] == 'Portfolio']
    
    series_to_plot = []
    
    # Helper function to calculate Base 100 series
    def get_base_100(row_returns):
        vals = [100.0]
        curr = 100.0
        for m in sorted_months:
            ret = row_returns[m]
            if pd.isna(ret) or ret == "-": 
                ret = 0.0
            curr = curr * (1 + float(ret))
            vals.append(curr)
        return vals

    # Add CDI (Benchmark)
    series_to_plot.append({
        'label': 'CDI (Benchmark)', 
        'values': get_base_100(cdi_returns), 
        'color': 'black', 
        'linewidth': 2, 
        'linestyle': '--'
    })

    # Add Portfolio
    if not portfolio.empty:
        series_to_plot.append({
            'label': 'Global Portfolio', 
            'values': get_base_100(portfolio.iloc[0]), 
            'color': '#FFB300', # XP Yellow/Amber
            'linewidth': 4
        })

    # Add Winners
    colors_win = ['#2ca02c', '#98df8a']
    for i, (idx, row) in enumerate(top_2.iterrows()):
        series_to_plot.append({
            'label': f"Top: {row['Name']}", 
            'values': get_base_100(row), 
            'color': colors_win[i % 2], 
            'alpha': 0.6
        })

    # Add Losers
    colors_loss = ['#d62728', '#ff9896']
    for i, (idx, row) in enumerate(bottom_2.iterrows()):
        series_to_plot.append({
            'label': f"Bottom: {row['Name']}", 
            'values': get_base_100(row), 
            'color': colors_loss[i % 2], 
            'alpha': 0.6
        })

    # Plotting
    plt.figure(figsize=(9.6, 6.4))
    ax = plt.gca()
    
    # X-axis labels
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    display_months = ["Início"]
    for m in sorted_months:
        y, mo = m.split('-')
        display_months.append(f"{month_names[int(mo)-1]}/{y[-2:]}")

    for s in series_to_plot:
        plt.plot(display_months, s['values'], label=s['label'], 
                 color=s.get('color'), 
                 linewidth=s.get('linewidth', 1.5), 
                 linestyle=s.get('linestyle', '-'),
                 alpha=s.get('alpha', 1.0))

    # Y-axis as percentage difference from 100
    from matplotlib.ticker import FuncFormatter
    def to_percent(y, position):
        return f"{int(y - 100)}%"
    ax.yaxis.set_major_formatter(FuncFormatter(to_percent))

    plt.title('Principais Eventos do Portfólio', fontsize=18, pad=80, fontweight='bold')
    plt.ylabel('') # Remove Y label
    plt.xlabel('') # Remove X label
    
    # Remove Grid and Spines (Borders)
    plt.grid(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    # Optional: leave bottom spine for timeline
    ax.spines['bottom'].set_color('#cccccc')
    
    # Legend at the top, horizontal
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=3, frameon=False, fontsize=10)
    
    plt.tight_layout()
    
    os.makedirs("outputs", exist_ok=True)
    chart_path = "outputs/performance_chart.png"
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Performance chart saved at {chart_path}")
    return chart_path
