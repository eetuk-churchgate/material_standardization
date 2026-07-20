"""
AI Material & Asset Standardization Engine
============================================
Multi-Provider LLM: Groq (free) → OpenAI → Rule-Based Fallback
International Standards: ISO 8000, ECLASS, UNSPSC, IEC 61360
Works with or without API keys
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
from datetime import datetime
from io import BytesIO

# Safe import with clear error message
try:
    from engine import MaterialAIEngine
except ImportError as e:
    st.error(f"❌ Cannot import engine module. Make sure engine.py is in the same folder.")
    st.error(f"Error details: {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Unexpected error loading engine: {e}")
    st.stop()

# ============================================================
# PAGE CONFIG - MUST be first Streamlit command
# ============================================================
st.set_page_config(
    page_title="AI Material Standardization Engine",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
DEFAULTS = {
    'engine': None,
    'materials_df': None,
    'assets_df': None,
    'audit_df': None,
    'review_df': None,
    'processed': False,
    'master_loaded': False,
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Initialize engine only once
if st.session_state.engine is None:
    st.session_state.engine = MaterialAIEngine()

engine = st.session_state.engine

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # --- LLM Status ---
    st.markdown("---")
    st.subheader("🧠 AI Engine")
    
    llm_name = engine.llm.get_provider_name()
    
    if llm_name == 'groq':
        st.success("🟢 Groq LLM (Free)")
        st.caption("Model: Llama 3.1 8B Instant")
    elif llm_name == 'openai':
        st.success("🔵 OpenAI LLM")
        st.caption("Model: GPT-4o Mini")
    else:
        st.warning("🟡 Rule-Based Mode")
        st.caption("Add API key for AI mode")
    
    st.markdown("---")
    
    # --- API Keys ---
    with st.expander("🔑 API Keys (Optional)", expanded=(llm_name == 'rule_based')):
        st.caption("Get free Groq key: console.groq.com")
        
        groq_key = st.text_input(
            "Groq API Key",
            type="password",
            value=os.getenv("GROQ_API_KEY", ""),
            placeholder="gsk_...",
            key="groq_key_input"
        )
        
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            placeholder="sk-...",
            key="openai_key_input"
        )
        
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔄 Reconnect", use_container_width=True, key="reconnect_btn"):
                st.session_state.engine = MaterialAIEngine()
                st.rerun()
        
        with col_btn2:
            if st.button("🧪 Test", use_container_width=True, key="test_btn"):
                test_engine = MaterialAIEngine()
                provider = test_engine.llm.get_provider_name()
                if provider != 'rule_based':
                    st.success(f"✅ Connected to {provider}")
                else:
                    st.error("No LLM connected")
    
    st.markdown("---")
    
    # --- Master Data Upload ---
    st.subheader("📚 Master Data (Teach Engine)")
    st.caption("Upload standardized Excel to improve matching")
    
    master_file = st.file_uploader(
        "Standardized Master Excel",
        type=['xlsx', 'xls'],
        key="master_upload"
    )
    
    if master_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(master_file.getvalue())
            master_path = tmp.name
        
        try:
            count = engine.learn_from_master(master_path)
            if count:
                st.session_state.master_loaded = True
                st.success(f"✅ Learned {count} names")
        except Exception as e:
            st.error(f"Error: {e}")
    
    if st.session_state.master_loaded:
        st.caption("📊 Master data active")
    
    st.markdown("---")
    
    # --- Confidence Threshold ---
    st.subheader("🎯 Review Threshold")
    threshold = st.slider(
        "Confidence % for review",
        min_value=50,
        max_value=95,
        value=70,
        key="threshold_slider"
    )
    engine.config['engine']['confidence_threshold'] = threshold
    
    st.markdown("---")
    
    # --- Processing Stats ---
    if st.session_state.processed:
        st.subheader("📊 Last Run")
        m = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        st.metric("Materials", m)
        st.metric("Assets", a)
        st.metric("Review", r)
    
    st.markdown("---")
    
    # --- Standards Reference ---
    with st.expander("🌍 Standards Reference"):
        st.markdown("""
        | Standard | Purpose |
        |----------|---------|
        | ISO 8000 | Data Quality |
        | ECLASS | Classification |
        | UNSPSC | Commodity Codes |
        | IEC 61360 | Electrical |
        | HSN | Tax/Customs |
        """)
    
    st.caption("v3.0 | Churchgate Group")

# ============================================================
# MAIN CONTENT
# ============================================================
st.title("🏗️ AI Material & Asset Standardization Engine")
st.markdown("### Messy Names → International Standard Format")

# Status bar
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    if engine.llm.get_provider_name() != 'rule_based':
        st.info(f"🧠 AI: {engine.llm.get_provider_name().upper()}")
    else:
        st.warning("🧠 Rule-Based Mode")
with col_s2:
    st.info("📚 Master: " + ("Loaded" if st.session_state.master_loaded else "None"))
with col_s3:
    st.info("🌍 ISO 8000 + ECLASS + HSN")

st.markdown("---")

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤 Upload & Process",
    "📊 Results",
    "⚠️ Review Queue",
    "📋 Audit Trail",
    "ℹ️ Help"
])

# ============================================================
# TAB 1: UPLOAD & PROCESS
# ============================================================
with tab1:
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 📤 Upload Your File")
        st.caption("Excel (.xlsx, .xls) or CSV")
        
        uploaded_file = st.file_uploader(
            "Choose file to standardize",
            type=['xlsx', 'xls', 'csv'],
            key="file_upload"
        )
    
    with col_right:
        st.markdown("### 📋 Expected Columns")
        st.caption("""
        - MaterialName / Name
        - MaterialType / Type
        - MaterialSubType / SubType
        - UOM / Unit
        - MaterialCode / Code
        """)
    
    if uploaded_file:
        st.markdown("---")
        
        # Preview
        try:
            if uploaded_file.name.endswith('.csv'):
                preview_df = pd.read_csv(uploaded_file)
            else:
                preview_df = pd.read_excel(uploaded_file)
            
            st.markdown(f"#### Preview: `{uploaded_file.name}`")
            st.dataframe(preview_df.head(10), use_container_width=True)
            st.caption(f"Rows: {len(preview_df)} | Columns: {len(preview_df.columns)}")
            
        except Exception as e:
            st.error(f"Error reading file: {e}")
            preview_df = None
        
        st.markdown("---")
        
        # Process button
        if st.button("🚀 Standardize Materials", type="primary", use_container_width=True):
            progress = st.progress(0, "Starting...")
            status = st.empty()
            
            try:
                status.info("Reading file...")
                progress.progress(10)
                
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                status.info("Processing with AI engine...")
                progress.progress(30)
                
                mat_df, ast_df, aud_df, rev_df = engine.process_file(tmp_path)
                
                progress.progress(80)
                status.info("Building output...")
                
                st.session_state.materials_df = mat_df
                st.session_state.assets_df = ast_df
                st.session_state.audit_df = aud_df
                st.session_state.review_df = rev_df
                st.session_state.processed = True
                
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
                progress.progress(100)
                status.empty()
                
                st.success("✅ Complete!")
                
                # Summary
                m_count = len(mat_df) if mat_df is not None else 0
                a_count = len(ast_df) if ast_df is not None else 0
                r_count = len(rev_df) if rev_df is not None else 0
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Materials", m_count)
                c2.metric("Assets", a_count)
                c3.metric("Need Review", r_count)
                
                st.info("👆 Go to **Results** tab to download")
                
            except Exception as e:
                progress.empty()
                status.empty()
                st.error(f"Error: {e}")

# ============================================================
# TAB 2: RESULTS
# ============================================================
with tab2:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    else:
        st.markdown("### 📊 Results")
        
        # Metrics
        m_count = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a_count = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r_count = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Materials", m_count)
        c2.metric("🏢 Assets", a_count)
        c3.metric("⚠️ Review", r_count)
        
        st.markdown("---")
        
        # Materials
        if m_count > 0:
            st.subheader("🔧 Standardized Materials")
            st.dataframe(st.session_state.materials_df, use_container_width=True, hide_index=True)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                buf = BytesIO()
                st.session_state.materials_df.to_excel(buf, index=False)
                st.download_button("📥 Excel", buf.getvalue(),
                                  "materials.xlsx", use_container_width=True)
            with col_d2:
                csv_data = st.session_state.materials_df.to_csv(index=False)
                st.download_button("📥 CSV", csv_data,
                                  "materials.csv", "text/csv", use_container_width=True)
        
        st.markdown("---")
        
        # Assets
        if a_count > 0:
            st.subheader("🏢 Standardized Assets")
            st.dataframe(st.session_state.assets_df, use_container_width=True, hide_index=True)
            
            col_d3, col_d4 = st.columns(2)
            with col_d3:
                buf = BytesIO()
                st.session_state.assets_df.to_excel(buf, index=False)
                st.download_button("📥 Excel", buf.getvalue(),
                                  "assets.xlsx", use_container_width=True)
            with col_d4:
                csv_data = st.session_state.assets_df.to_csv(index=False)
                st.download_button("📥 CSV", csv_data,
                                  "assets.csv", "text/csv", use_container_width=True)
        
        st.markdown("---")
        
        # Combined
        if m_count > 0 or a_count > 0:
            st.subheader("📦 Complete Report")
            combined = BytesIO()
            with pd.ExcelWriter(combined, engine='openpyxl') as w:
                if m_count > 0:
                    st.session_state.materials_df.to_excel(w, sheet_name='Materials', index=False)
                if a_count > 0:
                    st.session_state.assets_df.to_excel(w, sheet_name='Assets', index=False)
                if r_count > 0:
                    st.session_state.review_df.to_excel(w, sheet_name='Review', index=False)
                if st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
                    st.session_state.audit_df.to_excel(w, sheet_name='Audit', index=False)
            
            st.download_button(
                "📦 Download Complete Report",
                combined.getvalue(),
                f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                use_container_width=True
            )

# ============================================================
# TAB 3: REVIEW QUEUE
# ============================================================
with tab3:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    elif st.session_state.review_df is None or len(st.session_state.review_df) == 0:
        st.success("✅ All items processed with high confidence!")
    else:
        st.warning(f"### ⚠️ {len(st.session_state.review_df)} items need review")
        st.dataframe(st.session_state.review_df, use_container_width=True, hide_index=True)
        
        csv_data = st.session_state.review_df.to_csv(index=False)
        st.download_button("📥 Download Review CSV", csv_data,
                          "review_queue.csv", "text/csv")

# ============================================================
# TAB 4: AUDIT TRAIL
# ============================================================
with tab4:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    elif st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
        st.subheader("📋 Audit Trail")
        st.dataframe(st.session_state.audit_df, use_container_width=True, hide_index=True)
        
        csv_data = st.session_state.audit_df.to_csv(index=False)
        st.download_button("📥 Download Audit CSV", csv_data,
                          "audit_trail.csv", "text/csv")
    else:
        st.info("No audit data")

# ============================================================
# TAB 5: HELP
# ============================================================
with tab5:
    st.markdown("""
    ## ℹ️ How to Use
    
    ### Quick Start
    1. Upload Excel/CSV with old material names
    2. Click "Standardize Materials"
    3. Download results
    
    ### For Best Results
    - **Upload Master Data** (sidebar) → Engine learns your patterns
    - **Add Groq API Key** (free) → AI-powered mode
    
    ### LLM Options
    | Mode | Cost | Accuracy |
    |------|------|----------|
    | Rule-Based | Free | 60-75% |
    | Groq (Llama 3.1) | Free | 90-98% |
    | OpenAI (GPT-4o) | Paid | 90-98% |
    
    ### Output
    Materials: `CABLE-ARM-4C-16MM` | Assets: `VEHICLE-SEDAN-TOYOTA-CAMRY-ABC123`
    
    ### Standards
    ISO 8000 • ECLASS • UNSPSC • IEC 61360 • HSN
    """)

st.markdown("---")
st.caption("v3.0 | ISO 8000 • ECLASS • HSN | Churchgate Group")