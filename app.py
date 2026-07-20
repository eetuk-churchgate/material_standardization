"""
STREAMLIT UI - AI Material & Asset Standardization Engine
========================================================
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

from engine import MaterialAIEngine

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="AI Material & Asset Standardization Engine",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SESSION STATE INITIALIZATION
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
if 'master_loaded' not in st.session_state:
    st.session_state.master_loaded = False

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=80)
    st.title("⚙️ Configuration")
    
    # LLM Status Indicator
    st.markdown("---")
    st.subheader("🧠 AI Engine Status")
    
    llm_name = st.session_state.engine.llm.get_provider_name()
    
    if llm_name == 'groq':
        st.success("🟢 Groq LLM Active (Free Tier)")
        st.caption("Model: Llama 3.1 8B Instant")
    elif llm_name == 'openai':
        st.success("🔵 OpenAI LLM Active")
        st.caption("Model: GPT-4o Mini")
    else:
        st.warning("🟡 Rule-Based Mode (No LLM)")
        st.caption("Add API keys for AI-powered mode")
    
    st.markdown("---")
    
    # API Keys Section
    with st.expander("🔑 API Keys (Optional)", expanded=(llm_name == 'rule_based')):
        st.markdown("""
        **Add keys for AI-powered standardization:**
        - **Groq** (FREE): [console.groq.com](https://console.groq.com)
        - **OpenAI**: [platform.openai.com](https://platform.openai.com)
        """)
        
        groq_key = st.text_input(
            "Groq API Key",
            type="password",
            value=os.getenv("GROQ_API_KEY", ""),
            help="Free tier available at console.groq.com",
            placeholder="gsk_..."
        )
        
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Get from platform.openai.com",
            placeholder="sk-..."
        )
        
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔄 Reconnect LLM", use_container_width=True):
                st.session_state.engine = MaterialAIEngine()
                st.rerun()
        
        with col_btn2:
            if st.button("🧪 Test Connection", use_container_width=True):
                engine = MaterialAIEngine()
                provider = engine.llm.get_provider_name()
                if provider != 'rule_based':
                    st.success(f"✅ Connected to {provider}")
                else:
                    st.error("❌ No LLM connected")
    
    st.markdown("---")
    
    # Master Data Upload
    st.subheader("📚 Master Data (Teach the Engine)")
    st.caption("Upload your standardized Excel file so the engine learns your naming patterns")
    
    master_file = st.file_uploader(
        "Standardized Master Excel",
        type=['xlsx', 'xls'],
        key="master_upload",
        help="Upload your existing standardized materials for better matching"
    )
    
    if master_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(master_file.getvalue())
            master_path = tmp.name
        
        try:
            count = st.session_state.engine.learn_from_master(master_path)
            if count:
                st.session_state.master_loaded = True
                st.success(f"✅ Learned {count} standardized names")
        except Exception as e:
            st.error(f"Error loading master: {e}")
    
    if st.session_state.master_loaded:
        st.caption(f"📊 Master data loaded and indexed")
    
    st.markdown("---")
    
    # Confidence Threshold
    st.subheader("🎯 Confidence Threshold")
    threshold = st.slider(
        "Review Threshold %",
        min_value=50,
        max_value=95,
        value=70,
        help="Items below this confidence score will be flagged for human review"
    )
    st.session_state.engine.config['engine']['confidence_threshold'] = threshold
    
    st.markdown("---")
    
    # Processing Stats
    if st.session_state.processed:
        st.subheader("📊 Last Processing Stats")
        m = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        st.metric("Materials", m)
        st.metric("Assets", a)
        st.metric("Needs Review", r, delta=f"⚠️ {r}" if r > 0 else "✅ 0")
    
    st.markdown("---")
    
    # Standards Reference
    with st.expander("🌍 International Standards"):
        st.markdown("""
        This engine complies with:
        
        | Standard | Purpose |
        |----------|---------|
        | **ISO 8000** | Data Quality |
        | **ECLASS** | Product Classification |
        | **UNSPSC** | Commodity Codes |
        | **IEC 61360** | Electrical Naming |
        | **HSN** | Tax/Customs Codes |
        """)
    
    st.markdown("---")
    st.caption("v3.0 | Churchgate Group")

# ============================================================
# MAIN CONTENT
# ============================================================
st.title("🏗️ AI Material & Asset Standardization Engine")
st.markdown("### Transform messy material names → International Standard Format")

# Status bar
col_status1, col_status2, col_status3 = st.columns(3)
with col_status1:
    llm_display = st.session_state.engine.llm.get_provider_name()
    if llm_display == 'groq':
        st.info("🧠 AI Mode: Groq (Free)")
    elif llm_display == 'openai':
        st.info("🧠 AI Mode: OpenAI")
    else:
        st.warning("🧠 AI Mode: Rule-Based")
with col_status2:
    if st.session_state.master_loaded:
        st.success("📚 Master Data: Loaded")
    else:
        st.warning("📚 Master Data: None")
with col_status3:
    st.info("🌍 Standards: ISO 8000 + ECLASS + HSN")

st.markdown("---")

# Tabs
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
        st.markdown("### 📤 Upload Your Material File")
        st.markdown("Supported: **Excel (.xlsx, .xls)** or **CSV**")
        
        uploaded_file = st.file_uploader(
            "Choose a file to standardize",
            type=['xlsx', 'xls', 'csv'],
            key="file_upload",
            help="Upload your material master with old/unstandardized names"
        )
    
    with col_right:
        st.markdown("### 📋 Expected Columns")
        st.markdown("""
        Your file should contain:
        - `MaterialName` or `Name`
        - `MaterialType` or `Type`
        - `MaterialSubType` or `SubType`
        - `UOM` or `Unit`
        - `MaterialCode` or `Code`
        
        *Missing columns will be handled automatically.*
        """)
    
    if uploaded_file:
        st.markdown("---")
        
        # Preview uploaded data
        try:
            if uploaded_file.name.endswith('.csv'):
                preview_df = pd.read_csv(uploaded_file)
            else:
                preview_df = pd.read_excel(uploaded_file)
            
            st.markdown(f"#### 📄 File Preview: `{uploaded_file.name}`")
            
            col_p1, col_p2 = st.columns([3, 1])
            with col_p1:
                st.dataframe(preview_df.head(10), use_container_width=True)
            with col_p2:
                st.metric("Total Rows", len(preview_df))
                st.metric("Columns", len(preview_df.columns))
                st.markdown("**Columns Found:**")
                for col in preview_df.columns:
                    st.caption(f"• {col}")
        
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")
            preview_df = None
        
        st.markdown("---")
        
        # Process button
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        
        with col_btn2:
            process_btn = st.button(
                "🚀 Standardize Materials Now",
                type="primary",
                use_container_width=True,
                disabled=not uploaded_file
            )
        
        if process_btn and uploaded_file:
            progress_bar = st.progress(0, text="Starting...")
            status_text = st.empty()
            
            try:
                # Save uploaded file to temp
                status_text.info("📂 Reading file...")
                progress_bar.progress(10)
                
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                status_text.info("🔄 Processing with AI engine...")
                progress_bar.progress(30)
                
                # Process with engine
                mat_df, ast_df, aud_df, rev_df = st.session_state.engine.process_file(tmp_path)
                
                progress_bar.progress(80)
                status_text.info("📊 Building output files...")
                
                # Store in session state
                st.session_state.materials_df = mat_df
                st.session_state.assets_df = ast_df
                st.session_state.audit_df = aud_df
                st.session_state.review_df = rev_df
                st.session_state.processed = True
                
                # Cleanup temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
                progress_bar.progress(100)
                status_text.empty()
                
                st.success("✅ Standardization Complete!")
                st.balloons()
                
                # Quick summary
                m_count = len(mat_df) if mat_df is not None else 0
                a_count = len(ast_df) if ast_df is not None else 0
                r_count = len(rev_df) if rev_df is not None else 0
                
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("📦 Materials", m_count)
                col_s2.metric("🏢 Assets", a_count)
                col_s3.metric("⚠️ Need Review", r_count)
                
                # Average confidence
                all_conf = []
                if mat_df is not None and len(mat_df) > 0 and 'Confidence_Score' in mat_df.columns:
                    all_conf.extend(mat_df['Confidence_Score'].tolist())
                if ast_df is not None and len(ast_df) > 0 and 'Confidence_Score' in ast_df.columns:
                    all_conf.extend(ast_df['Confidence_Score'].tolist())
                
                avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0
                col_s4.metric("🎯 Avg Confidence", f"{avg_conf:.0f}%")
                
                st.info("👆 Go to **Results** tab to view and download")
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Processing error: {str(e)}")
                st.error("Please check your file format and try again.")

# ============================================================
# TAB 2: RESULTS
# ============================================================
with tab2:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first to see results here.")
        st.markdown("""
        ### How it works:
        1. **Upload** your Excel/CSV file with old material names
        2. **Process** with our AI engine
        3. **Download** standardized results ready for ERP
        
        *Optionally upload a master standardized file in the sidebar to improve accuracy.*
        """)
    else:
        st.markdown("### 📊 Standardization Results")
        
        # Summary metrics
        m_count = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a_count = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        r_count = len(st.session_state.review_df) if st.session_state.review_df is not None else 0
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        with col_m1:
            st.metric("📦 Materials", m_count)
        with col_m2:
            st.metric("🏢 Assets", a_count)
        with col_m3:
            if r_count > 0:
                st.metric("⚠️ Need Review", r_count, delta=f"{r_count} items")
            else:
                st.metric("⚠️ Need Review", 0)
        with col_m4:
            all_conf = []
            if st.session_state.materials_df is not None and len(st.session_state.materials_df) > 0:
                if 'Confidence_Score' in st.session_state.materials_df.columns:
                    all_conf.extend(st.session_state.materials_df['Confidence_Score'].tolist())
            if st.session_state.assets_df is not None and len(st.session_state.assets_df) > 0:
                if 'Confidence_Score' in st.session_state.assets_df.columns:
                    all_conf.extend(st.session_state.assets_df['Confidence_Score'].tolist())
            avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0
            st.metric("🎯 Avg Confidence", f"{avg_conf:.0f}%")
        
        st.markdown("---")
        
        # Materials Table
        if st.session_state.materials_df is not None and len(st.session_state.materials_df) > 0:
            st.markdown("#### 🔧 Standardized Materials")
            st.dataframe(
                st.session_state.materials_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Confidence_Score": st.column_config.ProgressColumn(
                        "Confidence",
                        format="%d%%",
                        min_value=0,
                        max_value=100
                    )
                }
            )
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                buf_mat = BytesIO()
                st.session_state.materials_df.to_excel(buf_mat, index=False, sheet_name='Materials')
                st.download_button(
                    label="📥 Download Materials (Excel)",
                    data=buf_mat.getvalue(),
                    file_name=f"standardized_materials_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_dl2:
                csv_mat = st.session_state.materials_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Materials (CSV)",
                    data=csv_mat,
                    file_name=f"standardized_materials_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Assets Table
        if st.session_state.assets_df is not None and len(st.session_state.assets_df) > 0:
            st.markdown("#### 🏢 Standardized Assets")
            st.dataframe(
                st.session_state.assets_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Confidence_Score": st.column_config.ProgressColumn(
                        "Confidence",
                        format="%d%%",
                        min_value=0,
                        max_value=100
                    )
                }
            )
            
            col_dl3, col_dl4 = st.columns(2)
            with col_dl3:
                buf_ast = BytesIO()
                st.session_state.assets_df.to_excel(buf_ast, index=False, sheet_name='Assets')
                st.download_button(
                    label="📥 Download Assets (Excel)",
                    data=buf_ast.getvalue(),
                    file_name=f"standardized_assets_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_dl4:
                csv_ast = st.session_state.assets_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Assets (CSV)",
                    data=csv_ast,
                    file_name=f"standardized_assets_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Combined Download
        if m_count > 0 or a_count > 0:
            st.markdown("#### 📦 Complete Report Download")
            
            combined_buffer = BytesIO()
            with pd.ExcelWriter(combined_buffer, engine='openpyxl') as writer:
                if m_count > 0:
                    st.session_state.materials_df.to_excel(writer, sheet_name='Materials', index=False)
                if a_count > 0:
                    st.session_state.assets_df.to_excel(writer, sheet_name='Assets', index=False)
                if r_count > 0:
                    st.session_state.review_df.to_excel(writer, sheet_name='Review_Queue', index=False)
                if st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
                    st.session_state.audit_df.to_excel(writer, sheet_name='Audit_Trail', index=False)
            
            st.download_button(
                label="📦 Download Complete Report (All Sheets)",
                data=combined_buffer.getvalue(),
                file_name=f"standardization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

# ============================================================
# TAB 3: REVIEW QUEUE
# ============================================================
with tab3:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    elif st.session_state.review_df is None or len(st.session_state.review_df) == 0:
        st.success("✅ All items standardized with high confidence! No review needed.")
        st.balloons()
    else:
        st.warning(f"### ⚠️ Review Queue: {len(st.session_state.review_df)} items need attention")
        st.markdown("These items had low confidence scores and may need manual verification.")
        
        st.dataframe(
            st.session_state.review_df,
            use_container_width=True,
            hide_index=True
        )
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            buf_rev = BytesIO()
            st.session_state.review_df.to_excel(buf_rev, index=False)
            st.download_button(
                label="📥 Download Review Queue (Excel)",
                data=buf_rev.getvalue(),
                file_name=f"review_queue_{datetime.now().strftime('%Y%m%d')}.xlsx",
                use_container_width=True
            )
        with col_r2:
            csv_rev = st.session_state.review_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Review Queue (CSV)",
                data=csv_rev,
                file_name=f"review_queue_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

# ============================================================
# TAB 4: AUDIT TRAIL
# ============================================================
with tab4:
    if not st.session_state.processed:
        st.info("👆 Upload and process a file first")
    elif st.session_state.audit_df is not None and len(st.session_state.audit_df) > 0:
        st.markdown("### 📋 Complete Audit Trail")
        st.markdown("Full traceability: Original Name → Standardized Name with confidence scores")
        
        st.dataframe(
            st.session_state.audit_df,
            use_container_width=True,
            hide_index=True
        )
        
        csv_aud = st.session_state.audit_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Audit Trail (CSV)",
            data=csv_aud,
            file_name=f"audit_trail_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No audit data available")

# ============================================================
# TAB 5: HELP
# ============================================================
with tab5:
    st.markdown("""
    ## ℹ️ How to Use This Engine
    
    ### Quick Start
    1. **Upload** your Excel/CSV file with old material names
    2. **Process** with the AI engine
    3. **Download** standardized results
    
    ### For Best Results
    - **Upload Master Data** (sidebar) → Engine learns your naming patterns
    - **Add API Key** (sidebar) → AI-powered standardization
    
    ### LLM Options
    | Provider | Cost | Quality |
    |----------|------|---------|
    | None (Rule-Based) | Free | 60-75% |
    | Groq (Llama 3.1) | Free | 90-98% |
    | OpenAI (GPT-4o Mini) | Paid | 90-98% |
    
    ### Output Format
    **Materials:**