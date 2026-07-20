"""
STREAMLIT UI - AI Material & Asset Standardization Engine
Multi-LLM support (Groq + OpenAI) with no-key fallback
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
from datetime import datetime
from io import BytesIO

from engine import MaterialAIEngine

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Material Standardization Engine",
    page_icon="🏗️",
    layout="wide"
)

# ============================================================
# SESSION STATE
# ============================================================
if 'engine' not in st.session_state:
    st.session_state.engine = MaterialAIEngine()
if 'materials_df' not in st.session_state:
    st.session_state.materials_df = None
if 'assets_df' not in st.session_state:
    st.session_state.assets_df = None
if 'audit_df' not in st.session_state:
    st.session_state.audit_df = None
if 'review_df' not in st.session_state:
    st.session_state.review_df = None
if 'processed' not in st.session_state:
    st.session_state.processed = False

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # LLM Status
    llm_name = st.session_state.engine.llm.get_provider_name()
    if llm_name == 'rule_based':
        st.warning("🟡 No LLM - Rule-based mode")
    elif llm_name == 'groq':
        st.success("🟢 Groq LLM (free tier)")
    elif llm_name == 'openai':
        st.success("🔵 OpenAI LLM")
    
    st.markdown("---")
    
    # API Keys
    with st.expander("🔑 API Keys (Optional)", expanded=False):
        groq_key = st.text_input("Groq API Key", type="password",
                                 value=os.getenv("GROQ_API_KEY", ""),
                                 help="Free tier: console.groq.com")
        openai_key = st.text_input("OpenAI API Key", type="password",
                                   value=os.getenv("OPENAI_API_KEY", ""))
        
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        
        if st.button("🔄 Reinitialize LLM"):
            st.session_state.engine = MaterialAIEngine()
            st.rerun()
    
    st.markdown("---")
    
    # Master Data Upload
    st.subheader("📚 Master Data")
    master_file = st.file_uploader("Upload standardized master", 
                                   type=['xlsx', 'xls'], key="master")
    
    if master_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(master_file.getvalue())
            master_path = tmp.name
        
        count = st.session_state.engine.learn_from_master(master_path)
        if count:
            st.success(f"✅ {count} names learned")
    
    st.markdown("---")
    
    # Confidence Threshold
    threshold = st.slider("Review Threshold %", 50, 95, 70)
    st.session_state.engine.config['engine']['confidence_threshold'] = threshold
    
    st.markdown("---")
    st.caption("ISO 8000 • ECLASS • UNSPSC • IEC 61360")

# ============================================================
# MAIN
# ============================================================
st.title("🏗️ AI Material & Asset Standardization Engine")
st.markdown("#### International Standards Compliant | Works with or without LLM")

tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Process", "📊 Results", "⚠️ Review", "📋 Audit"])

# --- TAB 1: Upload ---
with tab1:
    st.markdown("### Upload Your File")
    st.caption("Excel (.xlsx, .xls) or CSV")
    
    uploaded_file = st.file_uploader("Choose file", type=['xlsx', 'xls', 'csv'], key="file")
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                preview = pd.read_csv(uploaded_file)
            else:
                preview = pd.read_excel(uploaded_file)
            
            st.markdown(f"**Preview:** {uploaded_file.name}")
            st.dataframe(preview.head(10), use_container_width=True)
            st.caption(f"Rows: {len(preview)} | Columns: {list(preview.columns)}")
        except Exception as e:
            st.error(f"Error: {e}")
            preview = None
        
        st.markdown("---")
        
        if st.button("🚀 Process File", type="primary", use_container_width=True):
            with st.spinner("Processing..."):
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                mat_df, ast_df, aud_df, rev_df = st.session_state.engine.process_file(tmp_path)
                
                st.session_state.materials_df = mat_df
                st.session_state.assets_df = ast_df
                st.session_state.audit_df = aud_df
                st.session_state.review_df = rev_df
                st.session_state.processed = True
            
            st.success("✅ Complete!")
            st.balloons()

# --- TAB 2: Results ---
with tab2:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    else:
        # Metrics
        m = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Materials", m)
        c2.metric("Assets", a)
        c3.metric("Need Review", r)
        
        st.markdown("---")
        
        # Materials table
        if m > 0:
            st.markdown("#### 🔧 Standardized Materials")
            st.dataframe(st.session_state.materials_df, use_container_width=True, hide_index=True)
            
            buf = BytesIO()
            st.session_state.materials_df.to_excel(buf, index=False)
            st.download_button("📥 Download Materials", buf.getvalue(),
                              "standardized_materials.xlsx", use_container_width=True)
        
        st.markdown("---")
        
        # Assets table
        if a > 0:
            st.markdown("#### 🏢 Standardized Assets")
            st.dataframe(st.session_state.assets_df, use_container_width=True, hide_index=True)
            
            buf = BytesIO()
            st.session_state.assets_df.to_excel(buf, index=False)
            st.download_button("📥 Download Assets", buf.getvalue(),
                              "standardized_assets.xlsx", use_container_width=True)
        
        # Combined download
        if m > 0 or a > 0:
            st.markdown("---")
            combined = BytesIO()
            with pd.ExcelWriter(combined, engine='openpyxl') as w:
                if m > 0: st.session_state.materials_df.to_excel(w, sheet_name='Materials', index=False)
                if a > 0: st.session_state.assets_df.to_excel(w, sheet_name='Assets', index=False)
                if r > 0: st.session_state.review_df.to_excel(w, sheet_name='Review', index=False)
                if st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
                    st.session_state.audit_df.to_excel(w, sheet_name='Audit', index=False)
            
            st.download_button("📦 Download Complete Report", combined.getvalue(),
                              f"standardization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                              use_container_width=True)

# --- TAB 3: Review ---
with tab3:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    elif st.session_state.review_df is None or len(st.session_state.review_df) == 0:
        st.success("✅ All items processed with high confidence!")
    else:
        st.warning(f"⚠️ {len(st.session_state.review_df)} items need review")
        st.dataframe(st.session_state.review_df, use_container_width=True, hide_index=True)

# --- TAB 4: Audit ---
with tab4:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    elif st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
        st.markdown("### 📋 Audit Trail")
        st.dataframe(st.session_state.audit_df, use_container_width=True, hide_index=True)
        
        csv = st.session_state.audit_df.to_csv(index=False)
        st.download_button("📥 Download Audit CSV", csv, "audit_trail.csv", use_container_width=True)
    else:
        st.info("No audit data")