from fpdf import FPDF
from datetime import date
from sqlalchemy.orm import Session
from src.domain.models import Top20Portfolio, SymbolMaster, MonteCarloResult

class PDFReport(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'Ein Sof Lite - Daily Portfolio Report', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

class ReportingEngine:
    def __init__(self, session: Session):
        self.session = session
        
    def generate_daily_pdf_report(self) -> bytes:
        pdf = PDFReport()
        pdf.add_page()
        
        # 1. Title & Date
        report_date = date.today().strftime('%Y-%m-%d')
        pdf.set_font("helvetica", size=12)
        pdf.cell(0, 10, f"Date: {report_date}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        
        # 2. Portfolio Summary (Top 20)
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, "Top 20 Portfolio Allocations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", size=10)
        
        latest_top20 = self.session.query(Top20Portfolio).order_by(Top20Portfolio.date.desc()).first()
        if latest_top20:
            top20_date = latest_top20.date
            results = self.session.query(Top20Portfolio, SymbolMaster).join(
                SymbolMaster, Top20Portfolio.symbol_id == SymbolMaster.symbol_id
            ).filter(Top20Portfolio.date == top20_date).order_by(Top20Portfolio.final_rank.asc()).all()
            
            # Table Header
            pdf.set_font("helvetica", "B", 10)
            col_width = pdf.epw / 4
            pdf.cell(col_width, 10, "Rank", border=1)
            pdf.cell(col_width, 10, "Symbol", border=1)
            pdf.cell(col_width, 10, "Allocation (%)", border=1)
            pdf.cell(col_width, 10, "Score", border=1, new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", size=10)
            for item, symbol in results:
                pdf.cell(col_width, 10, str(item.final_rank), border=1)
                pdf.cell(col_width, 10, symbol.nse_ticker or symbol.symbol_id, border=1)
                
                alloc_str = f"{item.allocation_pct:.2f}%" if item.allocation_pct is not None else "0.00%"
                score_str = f"{item.ein_score:.2f}" if item.ein_score is not None else "0.00"
                
                pdf.cell(col_width, 10, alloc_str, border=1)
                pdf.cell(col_width, 10, score_str, border=1, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 10, "No Top 20 portfolio data available.", new_x="LMARGIN", new_y="NEXT")
            
        pdf.ln(10)
        
        # 3. Stress Test Results
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, "Latest Monte Carlo Stress Test Results", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", size=10)
        
        stress_result = self.session.query(MonteCarloResult).order_by(MonteCarloResult.date.desc()).first()
        if stress_result:
            pdf.cell(0, 8, f"Date: {stress_result.date}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 8, f"Status: {stress_result.status}", new_x="LMARGIN", new_y="NEXT")
            
            cvar_125d = stress_result.tail_risk_metrics.get("125d", {}).get("cvar_95", 0)
            pdf.cell(0, 8, f"125-Day CVaR (95%): {cvar_125d*100:.2f}%", new_x="LMARGIN", new_y="NEXT")
            
            prob_dd_20 = stress_result.loss_probabilities.get("125d", {}).get("dd_20pct", 0)
            pdf.cell(0, 8, f"125-Day Prob of >20% Drawdown: {prob_dd_20*100:.2f}%", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", "I", 8)
            pdf.cell(0, 8, f"Reproducibility Seed: {stress_result.seed_hash}", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 10, "No stress test data available.", new_x="LMARGIN", new_y="NEXT")
            
        # Write to bytes (fpdf2 returns a bytearray when output() is called without a filename and dest="S")
        pdf_bytes = pdf.output()
        return pdf_bytes
