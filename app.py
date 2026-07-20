"""
AI Material & Asset Standardization Engine
============================================
Multi-Provider LLM: Groq (free) -> OpenAI -> Rule-Based Fallback
International Standards: ISO 8000, ECLASS, UNSPSC, IEC 61360
Batch Processing with Live Progress
Persistent Master Data (survives refresh/reboot)
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
from datetime import datetime
from io import BytesIO

try:
    from engine import MaterialAIEngine
except Exception as e:
    st.error(f"Cannot load engine: {e}")
    st.stop()

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Material Standardization Engine",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SESSION STATE
# ============================================================
if 'engine' not in st.session_state:
    st.session_state.engine = MaterialAIEngine()
    if len(st.session_state.engine.master_names) > 0:
        st.session_state.master_loaded = True
    else:
        st.session_state.master_loaded = False

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

engine = st.session_state.engine

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("Configuration")
    
    # LLM Status
    st.markdown("---")
    st.subheader("AI Engine Status")
    
    llm_name = engine.llm.get_provider_name()
    
    if llm_name == 'groq':
        st.success("Groq LLM Active (Free Tier)")
        st.caption("Model: Llama 3.1 8B Instant")
    elif llm_name == 'openai':
        st.success("OpenAI LLM Active")
        st.caption("Model: GPT-4o Mini")
    else:
        st.warning("Rule-Based Mode (No LLM)")
        st.caption("Add API keys for AI-powered mode")
    
    st.markdown("---")
    
    # API Keys
    with st.expander("API Keys (Optional)", expanded=(llm_name == 'rule_based')):
        st.markdown("Get free Groq key: console.groq.com")
        
        groq_key = st.text_input(
            "Groq API Key",
            type="password",
            value=os.getenv("GROQ_API_KEY", ""),
            placeholder="gsk_...",
            key="groq_key"
        )
        
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            placeholder="sk-...",
            key="openai_key"
        )
        
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reconnect LLM", use_container_width=True):
                st.session_state.engine = MaterialAIEngine()
                if len(st.session_state.engine.master_names) > 0:
                    st.session_state.master_loaded = True
                st.rerun()
        with col2:
            if st.button("Test Connection", use_container_width=True):
                test_engine = MaterialAIEngine()
                provider = test_engine.llm.get_provider_name()
                if provider != 'rule_based':
                    st.success(f"Connected to {provider}")
                else:
                    st.error("No LLM connected")
    
    st.markdown("---")
    
    # Master Data Upload
    st.subheader("Master Data (Teach Engine)")
    st.caption("Upload standardized Excel files. Upload multiple to combine knowledge. Data persists across sessions.")
    
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
                st.success(f"Added {count} names! Total: {len(engine.master_names)}")
        except Exception as e:
            st.error(f"Error loading master: {e}")
    
    if st.session_state.master_loaded:
        st.info(f"Total learned: {len(engine.master_names)} names")
    
    # Clear master data
    if st.session_state.master_loaded:
        if st.button("Clear All Master Data", use_container_width=True):
            engine.clear_master_data()
            st.session_state.master_loaded = False
            st.success("Master data cleared!")
            st.rerun()
    
    st.markdown("---")
    
    # Confidence Threshold
    st.subheader("Review Threshold")
    threshold = st.slider(
        "Confidence % for review",
        min_value=50,
        max_value=95,
        value=70,
        help="Items below this confidence will be flagged for human review"
    )
    engine.config['engine']['confidence_threshold'] = threshold
    
    st.markdown("---")
    
    # Processing Stats
    if st.session_state.processed:
        st.subheader("Last Processing")
        m = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        st.metric("Materials", m)
        st.metric("Assets", a)
        if r > 0:
            st.metric("Need Review", r)
        else:
            st.metric("Need Review", 0)
    
    st.markdown("---")
    
    with st.expander("International Standards"):
        st.markdown("""
        | Standard | Purpose |
        |----------|---------|
        | ISO 8000 | Data Quality |
        | ECLASS | Product Classification |
        | UNSPSC | Commodity Codes |
        | IEC 61360 | Electrical Naming |
        | HSN | Tax/Customs |
        """)
    
    st.caption("v3.0 | Churchgate Group")

# ============================================================
# MAIN CONTENT
# ============================================================
st.title("Material & Asset Standardization Engine")
st.markdown("### Transform messy material names into International Standard Format")

# Status bar
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    llm_display = engine.llm.get_provider_name()
    if llm_display == 'groq':
        st.info("AI: Groq (Free)")
    elif llm_display == 'openai':
        st.info("AI: OpenAI")
    else:
        st.warning("AI: Rule-Based")
with col_s2:
    master_count = len(engine.master_names)
    if master_count > 0:
        st.success(f"Master: {master_count} names")
    else:
        st.warning("Master: None")
with col_s3:
    st.info("Standards: ISO 8000 + ECLASS + HSN")

st.markdown("---")

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Upload & Process",
    "Results",
    "Review Queue",
    "Audit Trail",
    "Help"
])

# ============================================================
# TAB 1: UPLOAD & PROCESS
# ============================================================
with tab1:
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### Upload Your Material File")
        st.markdown("Supported formats: Excel (.xlsx, .xls) or CSV")
        
        uploaded_file = st.file_uploader(
            "Choose a file to standardize",
            type=['xlsx', 'xls', 'csv'],
            key="file_upload"
        )
    
    with col_right:
        st.markdown("### Expected Columns")
        st.markdown("""
        - MaterialName or Name
        - MaterialType or Type
        - MaterialSubType or SubType
        - UOM or Unit
        - MaterialCode or Code
        
        Missing columns handled automatically.
        """)
    
    if uploaded_file:
        st.markdown("---")
        
        # Preview
        try:
            if uploaded_file.name.endswith('.csv'):
                preview_df = pd.read_csv(uploaded_file)
            else:
                preview_df = pd.read_excel(uploaded_file)
            
            st.markdown(f"#### Preview: {uploaded_file.name}")
            st.dataframe(preview_df.head(10), use_container_width=True)
            st.caption(f"Total rows: {len(preview_df)} | Columns: {list(preview_df.columns)}")
            
        except Exception as e:
            st.error(f"Error reading file: {e}")
            preview_df = None
        
        st.markdown("---")
        
        # Process Button
        if st.button("Standardize Materials Now", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="Starting...")
            status_text = st.empty()
            
            try:
                status_text.info("Reading file...")
                
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                # Set progress callback
                def update_progress(pct, msg):
                    progress_bar.progress(pct, text=msg)
                
                engine.set_progress_callback(update_progress)
                
                status_text.info("Processing in batches...")
                
                mat_df, ast_df, aud_df, rev_df = engine.process_file(tmp_path)
                
                progress_bar.progress(100, text="Complete!")
                
                st.session_state.materials_df = mat_df
                st.session_state.assets_df = ast_df
                st.session_state.audit_df = aud_df
                st.session_state.review_df = rev_df
                st.session_state.processed = True
                
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
                status_text.empty()
                
                st.success("Standardization Complete!")
                st.balloons()
                
                # Quick Summary
                m_count = len(mat_df) if mat_df is not None else 0
                a_count = len(ast_df) if ast_df is not None else 0
                r_count = len(rev_df) if rev_df is not None else 0
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Materials", m_count)
                c2.metric("Assets", a_count)
                c3.metric("Need Review", r_count)
                
                all_conf = []
                if mat_df is not None and len(mat_df) > 0 and 'Confidence_Score' in mat_df.columns:
                    all_conf.extend(mat_df['Confidence_Score'].tolist())
                if ast_df is not None and len(ast_df) > 0 and 'Confidence_Score' in ast_df.columns:
                    all_conf.extend(ast_df['Confidence_Score'].tolist())
                avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0
                c4.metric("Avg Confidence", f"{avg_conf:.0f}%")
                
                st.info("Go to Results tab to view and download")
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"Processing error: {e}")

# ============================================================
# TAB 2: RESULTS
# ============================================================
with tab2:
    if not st.session_state.processed:
        st.info("Upload and process a file first to see results")
    else:
        st.markdown("### Standardization Results")
        
        m_count = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a_count = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r_count = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Materials", m_count)
        col_m2.metric("Assets", a_count)
        col_m3.metric("Need Review", r_count)
        
        st.markdown("---")
        
        # Materials Table
        if m_count > 0:
            st.markdown("#### Standardized Materials")
            st.dataframe(st.session_state.materials_df, use_container_width=True, hide_index=True)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                buf_mat = BytesIO()
                st.session_state.materials_df.to_excel(buf_mat, index=False, sheet_name='Materials')
                st.download_button(
                    "Download Materials (Excel)",
                    buf_mat.getvalue(),
                    f"standardized_materials_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    use_container_width=True
                )
            with col_d2:
                csv_mat = st.session_state.materials_df.to_csv(index=False)
                st.download_button(
                    "Download Materials (CSV)",
                    csv_mat,
                    f"standardized_materials_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Assets Table
        if a_count > 0:
            st.markdown("#### Standardized Assets")
            st.dataframe(st.session_state.assets_df, use_container_width=True, hide_index=True)
            
            col_d3, col_d4 = st.columns(2)
            with col_d3:
                buf_ast = BytesIO()
                st.session_state.assets_df.to_excel(buf_ast, index=False, sheet_name='Assets')
                st.download_button(
                    "Download Assets (Excel)",
                    buf_ast.getvalue(),
                    f"standardized_assets_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    use_container_width=True
                )
            with col_d4:
                csv_ast = st.session_state.assets_df.to_csv(index=False)
                st.download_button(
                    "Download Assets (CSV)",
                    csv_ast,
                    f"standardized_assets_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Combined Download
        if m_count > 0 or a_count > 0:
            st.markdown("#### Complete Report")
            combined = BytesIO()
            with pd.ExcelWriter(combined, engine='openpyxl') as writer:
                if m_count > 0:
                    st.session_state.materials_df.to_excel(writer, sheet_name='Materials', index=False)
                if a_count > 0:
                    st.session_state.assets_df.to_excel(writer, sheet_name='Assets', index=False)
                if r_count > 0:
                    st.session_state.review_df.to_excel(writer, sheet_name='Review_Queue', index=False)
                if st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
                    st.session_state.audit_df.to_excel(writer, sheet_name='Audit_Trail', index=False)
            
            st.download_button(
                "Download Complete Report (All Sheets)",
                combined.getvalue(),
                f"standardization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                use_container_width=True
            )

# ============================================================
# TAB 3: REVIEW QUEUE
# ============================================================
with tab3:
    if not st.session_state.processed:
        st.info("Upload and process a file first")
    elif st.session_state.review_df is None or len(st.session_state.review_df) == 0:
        st.success("All items standardized with high confidence!")
    else:
        st.warning(f"{len(st.session_state.review_df)} items need review")
        st.dataframe(st.session_state.review_df, use_container_width=True, hide_index=True)
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            buf = BytesIO()
            st.session_state.review_df.to_excel(buf, index=False)
            st.download_button("Download Excel", buf.getvalue(), "review_queue.xlsx")
        with col_r2:
            csv_data = st.session_state.review_df.to_csv(index=False)
            st.download_button("Download CSV", csv_data, "review_queue.csv", "text/csv")

# ============================================================
# TAB 4: AUDIT TRAIL
# ============================================================
with tab4:
    if not st.session_state.processed:
        st.info("Upload and process a file first")
    elif st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
        st.markdown("### Audit Trail")
        st.markdown("Complete original to standardized mapping")
        st.dataframe(st.session_state.audit_df, use_container_width=True, hide_index=True)
        
        csv_data = st.session_state.audit_df.to_csv(index=False)
        st.download_button(
            "Download Audit Trail (CSV)",
            csv_data,
            f"audit_trail_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
    else:
        st.info("No audit data")

# ============================================================
# TAB 5: HELP
# ============================================================
with tab5:
    st.markdown("""
    ## How to Use This Engine
    
    ### Quick Start
    1. Upload Master Data in sidebar first (teaches the engine your naming patterns)
    2. Upload your Excel/CSV file with old material names
    3. Click "Standardize Materials Now"
    4. Download standardized results
    
    ### Master Data Persistence
    - Master data is saved automatically and survives page refreshes
    - Upload multiple files to combine knowledge
    - Use "Clear All Master Data" to reset
    
    ### LLM Options
    | Provider | Cost | Accuracy |
    |----------|------|----------|
    | None (Rule-Based) | Free | 60-75% |
    | Groq (Llama 3.1) | Free | 90-98% |
    | OpenAI (GPT-4o Mini) | Paid | 90-98% |
    
    ### Output Format
    Materials:
    MAT-00001 | CABLE-ARM-4C-16MM | CABLE | 8544 | METER | 95%
    
    Assets:
    AST-00001 | VEHICLE-SEDAN-TOYOTA-CAMRY-BDG934BQ | VEHICLE | 8703 | 98%
    
    ### International Standards
    - ISO 8000 -- Data Quality Management
    - ECLASS -- Product Classification Standard
    - UNSPSC -- UN Standard Products and Services Code
    - IEC 61360 -- Electrical Component Data Dictionary
    - HSN -- Harmonized System Nomenclature
    """)

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.caption(
    "AI Material and Asset Standardization Engine v3.0 | "
    "ISO 8000, ECLASS, UNSPSC, IEC 61360 | "
    "Churchgate Group"
)