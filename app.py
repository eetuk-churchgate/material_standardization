"""
AI Material & Asset Standardization Engine
============================================
Dual Mode: Convert Format + HSN (Fast) OR AI Standardize (Smart)
Multi-Provider LLM: Groq (free) -> OpenAI -> Rule-Based Fallback
International Standards: ISO 8000, ECLASS, UNSPSC, IEC 61360
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
    
    # Processing Mode
    st.markdown("---")
    st.subheader("Processing Mode")
    
    mode = st.radio(
        "Choose mode:",
        ["Convert Format + HSN (Fast)", "AI Standardize (Smart)"],
        index=0,
        help="Convert: For already-standardized files that need HSN codes.\nAI Standardize: For raw/unstandardized files."
    )
    
    if "Convert" in mode:
        engine.set_mode("convert")
    else:
        engine.set_mode("standardize")
    
    if "Convert" in mode:
        st.success("Mode: Fast Convert + HSN")
        st.caption("Instant format conversion + HSN assignment")
    else:
        st.info("Mode: AI Standardize")
        st.caption("AI-powered with master matching + LLM")
    
    st.markdown("---")
    
    # LLM Status
    st.subheader("AI Engine Status")
    
    llm_name = engine.llm.get_provider_name()
    
    if llm_name == 'groq':
        st.success("Groq LLM Active (Free Tier)")
    elif llm_name == 'openai':
        st.success("OpenAI LLM Active")
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
    
    # Master Data Upload (only for AI Standardize mode)
    if "AI" in mode:
        st.subheader("Master Data (Teach Engine)")
        st.caption("Upload standardized Excel files to improve AI accuracy.")
        
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
        
        # Backup download
        if st.session_state.master_loaded and len(engine.master_names) > 0:
            backup_df = pd.DataFrame({'Standardized_Name': engine.master_names})
            backup_data = BytesIO()
            backup_df.to_excel(backup_data, index=False)
            backup_data.seek(0)
            
            st.download_button(
                f"Download Backup ({len(engine.master_names)} names)",
                backup_data,
                "master_backup.xlsx",
                use_container_width=True
            )
        
        # Clear button
        if st.session_state.master_loaded:
            if st.button("Clear Master Data", use_container_width=True):
                engine.clear_master_data()
                st.session_state.master_loaded = False
                st.success("Master data cleared!")
                st.rerun()
    
    st.markdown("---")
    
    # Confidence Threshold (only for AI Standardize mode)
    if "AI" in mode:
        st.subheader("Review Threshold")
        threshold = st.slider(
            "Confidence % for review",
            min_value=50,
            max_value=95,
            value=70
        )
        engine.config['engine']['confidence_threshold'] = threshold
    
    st.markdown("---")
    
    # Processing Stats
    if st.session_state.processed:
        st.subheader("Last Processing")
        m = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        
        st.metric("Materials", m)
        st.metric("Assets", a)
    
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
    if "Convert" in mode:
        st.success("Mode: Fast Convert + HSN")
    else:
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
tab1, tab2, tab3 = st.tabs([
    "Upload & Process",
    "Results",
    "Help"
])

# ============================================================
# TAB 1: UPLOAD & PROCESS
# ============================================================
with tab1:
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### Upload Your File")
        st.markdown("Supported formats: Excel (.xlsx, .xls) or CSV")
        
        if "Convert" in mode:
            st.info("Mode: **Convert Format + HSN** — For already-standardized files. Assigns HSN codes and converts to ERP format.")
        else:
            st.info("Mode: **AI Standardize** — For raw/unstandardized files. AI-powered standardization from scratch.")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['xlsx', 'xls', 'csv'],
            key="file_upload"
        )
    
    with col_right:
        st.markdown("### Expected Columns")
        if "Convert" in mode:
            st.markdown("""
            - Standardized_Name
            - Category or Material_Type
            - Sub-Category or Material_Subtype
            - UOM
            - Material_Code (optional)
            
            Missing columns handled automatically.
            """)
        else:
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
        button_label = "Convert Format + Assign HSN" if "Convert" in mode else "Standardize Materials Now"
        
        if st.button(button_label, type="primary", use_container_width=True):
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
                
                status_text.info("Processing...")
                
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
                
                st.success("Complete!")
                st.balloons()
                
                # Quick Summary
                m_count = len(mat_df) if mat_df is not None else 0
                a_count = len(ast_df) if ast_df is not None else 0
                
                c1, c2 = st.columns(2)
                c1.metric("Rows Processed", m_count + a_count)
                c2.metric("Output Columns", len(mat_df.columns) if mat_df is not None and len(mat_df) > 0 else 0)
                
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
        st.markdown("### Results")
        
        m_count = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a_count = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Materials", m_count)
        col_m2.metric("Assets", a_count)
        
        st.markdown("---")
        
        # Main output table
        if m_count > 0:
            st.markdown("#### Standardized Data")
            st.dataframe(st.session_state.materials_df, use_container_width=True, hide_index=True)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                buf = BytesIO()
                st.session_state.materials_df.to_excel(buf, index=False, sheet_name='Materials')
                st.download_button(
                    "Download Excel",
                    buf.getvalue(),
                    f"standardized_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    use_container_width=True
                )
            with col_d2:
                csv_data = st.session_state.materials_df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv_data,
                    f"standardized_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )
        
        # Assets table
        if a_count > 0:
            st.markdown("---")
            st.markdown("#### Assets")
            st.dataframe(st.session_state.assets_df, use_container_width=True, hide_index=True)
            
            buf = BytesIO()
            st.session_state.assets_df.to_excel(buf, index=False)
            st.download_button("Download Assets", buf.getvalue(), "assets.xlsx")

# ============================================================
# TAB 3: HELP
# ============================================================
with tab3:
    st.markdown("""
    ## How to Use This Engine
    
    ### Two Modes Available:
    
    **Convert Format + HSN (Fast)**
    - For files that are already standardized but need:
      - HSN codes assigned
      - Column format converted to ERP standard
      - UOM standardization
    - Processing time: Seconds
    
    **AI Standardize (Smart)**
    - For raw/unstandardized files
    - Uses master data matching + rule-based extraction
    - Upload master data to improve accuracy
    - Processing time: Minutes
    
    ### Output Format (ERP Ready):
    
    | Column | Example |
    |--------|---------|
    | Material_ID | MAT-00001 |
    | Standardized Material_Type | CABLE |
    | Standardized Material_Subtype | ARMOURED |
    | Standardized Material_Name | CABLE-ARM-4C-16MM |
    | Material_Code | M0216 |
    | UOM | METER |
    | HSN_Code | 8544 |
    | Status | Active |
    
    ### International Standards:
    - ISO 8000 -- Data Quality Management
    - ECLASS -- Product Classification Standard
    - UNSPSC -- UN Standard Products and Services Code
    - IEC 61360 -- Electrical Component Data Dictionary
    - HSN -- Harmonized System Nomenclature
    
    ### Need Help?
    Contact the Technology and Automation Team
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