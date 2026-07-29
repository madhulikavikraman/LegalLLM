"""
Infographic builders using Plotly (free, no external service calls).
All charts are returned as plotly Figure objects for Streamlit (st.plotly_chart)
and can also be exported to PNG via kaleido for the PDF report.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

SEVERITY_COLORS = {3: "#e63946", 2: "#f4a261", 1: "#e9c46a"}
SEVERITY_NAMES = {3: "High", 2: "Medium", 1: "Low"}


def risk_gauge(score: int, label: str):
    color = "#e63946" if score >= 70 else "#f4a261" if score >= 35 else "#2a9d8f"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": " / 100", "font": {"size": 40}},
        title={"text": f"Overall Lease Risk<br><span style='font-size:0.8em;color:{color}'>{label}</span>"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 35], "color": "#eafaf1"},
                {"range": [35, 70], "color": "#fef3e2"},
                {"range": [70, 100], "color": "#fdecea"},
            ],
        },
    ))
    fig.update_layout(height=320, margin=dict(l=30, r=30, t=70, b=10))
    return fig


def severity_breakdown_chart(findings):
    if not findings:
        fig = go.Figure()
        fig.add_annotation(text="No risky clauses detected", showarrow=False, font=dict(size=16))
        fig.update_layout(height=320)
        return fig
    counts = {3: 0, 2: 0, 1: 0}
    for f in findings:
        counts[f["severity"]] += 1
    df = pd.DataFrame({
        "Severity": [SEVERITY_NAMES[s] for s in counts if counts[s] > 0],
        "Count": [counts[s] for s in counts if counts[s] > 0],
        "color": [SEVERITY_COLORS[s] for s in counts if counts[s] > 0],
    })
    fig = px.pie(df, names="Severity", values="Count", color="Severity",
                 color_discrete_map={"High": SEVERITY_COLORS[3], "Medium": SEVERITY_COLORS[2], "Low": SEVERITY_COLORS[1]},
                 hole=0.45, title="Risky Clauses by Severity")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def clause_coverage_chart(present, missing):
    total = len(present) + len(missing)
    df = pd.DataFrame({
        "Clause": present + missing,
        "Status": ["Present"] * len(present) + ["Missing"] * len(missing),
    })
    fig = px.bar(
        df.sort_values("Status"), y="Clause", x=[1] * total, color="Status",
        color_discrete_map={"Present": "#2a9d8f", "Missing": "#e76f51"},
        orientation="h", title="Standard Clause Coverage Checklist",
    )
    fig.update_layout(
        height=max(400, total * 26), xaxis=dict(showticklabels=False, title=None),
        yaxis_title=None, margin=dict(l=10, r=10, t=50, b=10), legend_title=None,
    )
    return fig


def risky_clause_bar(findings):
    if not findings:
        fig = go.Figure()
        fig.add_annotation(text="No risky clauses detected", showarrow=False, font=dict(size=16))
        fig.update_layout(height=320)
        return fig
    df = pd.DataFrame({
        "Clause": [f["label"] for f in findings],
        "Severity": [f["severity"] for f in findings],
        "SeverityName": [SEVERITY_NAMES[f["severity"]] for f in findings],
    }).sort_values("Severity")
    fig = px.bar(
        df, y="Clause", x="Severity", color="SeverityName", orientation="h",
        color_discrete_map={"High": SEVERITY_COLORS[3], "Medium": SEVERITY_COLORS[2], "Low": SEVERITY_COLORS[1]},
        title="Detected Risky Clauses (by severity)",
    )
    fig.update_layout(
        height=max(320, len(findings) * 40), xaxis=dict(showticklabels=False, title=None),
        yaxis_title=None, margin=dict(l=10, r=10, t=50, b=10), legend_title=None,
    )
    return fig


def rent_deposit_chart(rent_val, deposit_val):
    if not rent_val and not deposit_val:
        fig = go.Figure()
        fig.add_annotation(text="Rent/deposit amounts not found", showarrow=False, font=dict(size=16))
        fig.update_layout(height=280)
        return fig
    labels, values = [], []
    if rent_val:
        labels.append("Monthly Rent"); values.append(rent_val)
    if deposit_val:
        labels.append("Security Deposit"); values.append(deposit_val)
    fig = px.bar(x=labels, y=values, text=values, color=labels,
                 color_discrete_sequence=["#264653", "#2a9d8f"], title="Key Amounts ($)")
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig.update_layout(height=320, showlegend=False, xaxis_title=None, yaxis_title="USD",
                       margin=dict(l=10, r=10, t=50, b=10))
    return fig
