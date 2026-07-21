"""
🏗️ AI MATERIAL & ASSET STANDARDIZATION ENGINE
===========================================================
Quick Lookup | Batch Processing | Duplicate Detection | Quality Scoring
Multi-Format Export | Enterprise Audit Ready
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
from datetime import datetime
from io import BytesIO
import json

try:
    from engine import MaterialAIEngine
except Exception as e:
    st.error(f"Cannot load engine: {e}")
    st.stop()

st.set_page_config(page_title="Enterprise Material Engine", page_icon="🏗️", layout="wide")

# Session State
if 'engine' not in st.session_state:
    st.session_state.engine = MaterialAIEngine()
    st.session_state.master_loaded = len(st.session_state.engine.master_names) > 0
if 'materials_df' not in st.session_state: st.session_state.materials_df = None
if 'assets_df' not in st.session_state: st.session_state.assets_df = None
if 'duplicates_df' not in st.session_state: st.session_state.duplicates_df = None
if 'processed' not in st.session_state: st.session_state.processed = False
if 'lookup_result' not in st.session_state: st.session_state.lookup_result = None

engine = st.session_state.engine

# ================================================================
# SIDEBAR
# ================================================================
with st.sidebar:
    st.title("🏗️ Enterprise Engine")
    
    # Quality Score
    if st.session_state.processed:
        quality = engine.get_quality_report()
        st.metric("Data Quality", f"{quality['quality_score']}%")
    
    st.markdown("---")
    
    # Mode Selector
    st.subheader("⚡ Processing Mode")
    mode = st.radio("Choose mode:", ["Convert Format + HSN (Fast)", "AI Standardize (Smart)"], index=0)
    engine.set_mode("convert" if "Convert" in mode else "standardize")
    
    if "Convert" in mode:
        st.success("⚡ Fast Mode")
    else:
        st.info("🧠 AI Mode")
    
    st.markdown("---")
    
    # LLM Status
    llm_name = engine.llm.get_provider_name()
    if llm_name == 'groq': st.success("🟢 Groq LLM (Free)")
    elif llm_name == 'openai': st.success("🔵 OpenAI LLM")
    else: st.warning("🟡 Rule-Based")
    
    st.markdown("---")
    
    # API Keys
    with st.expander("🔑 API Keys"):
        groq_key = st.text_input("Groq Key", type="password", value=os.getenv("GROQ_API_KEY", ""))
        openai_key = st.text_input("OpenAI Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        if groq_key: os.environ["GROQ_API_KEY"] = groq_key
        if openai_key: os.environ["OPENAI_API_KEY"] = openai_key
        if st.button("Reconnect"): st.session_state.engine = MaterialAIEngine(); st.rerun()
    
    st.markdown("---")
    
    # Master Data
    if "AI" in mode:
        st.subheader("📚 Master Data")
        master_file = st.file_uploader("Upload Master", type=['xlsx', 'xls'], key="master")
        if master_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp.write(master_file.getvalue())
            count = engine.learn_from_master(tmp.name)
            if count: st.session_state.master_loaded = True; st.success(f"+{count} names | Total: {len(engine.master_names)}")
        
        if st.session_state.master_loaded:
            st.info(f"📊 {len(engine.master_names)} names")
            if st.button("Clear Master"): engine.clear_master_data(); st.session_state.master_loaded = False; st.rerun()
    
    st.markdown("---")
    with st.expander("🌍 Standards"):
        st.markdown("ISO 8000 | ECLASS | UNSPSC | IEC 61360 | HSN")
    st.caption("v4.0 Enterprise | Churchgate Group")

# ================================================================
# MAIN
# ================================================================
st.title("🏗️ Enterprise Material Standardization Engine")
st.markdown("### Fortune 500 Grade | AI-Powered | Audit Ready")

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1:
    if "Convert" in mode: st.success("⚡ Fast Convert")
    else:
        if engine.llm.get_provider_name() == 'groq': st.info("🧠 Groq AI")
        elif engine.llm.get_provider_name() == 'openai': st.info("🧠 OpenAI")
        else: st.warning("🧠 Rule-Based")
with col_s2: st.info(f"📚 Master: {len(engine.master_names)}")
with col_s3: st.info("🌍 ISO 8000 + HSN")
with col_s4:
    if st.session_state.processed:
        st.metric("Quality", f"{engine.quality_score}%")

st.markdown("---")

# Tabs
tab0, tab1, tab2, tab3 = st.tabs(["🔍 Quick Lookup", "📤 Batch Process", "📊 Results", "ℹ️ Help"])

# ================================================================
# TAB 0: QUICK LOOKUP
# ================================================================
with tab0:
    st.markdown("### 🔍 Single Item Standardization")
    st.caption("Paste any name - get instant standardized output")
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        lookup_name = st.text_input("Material Name", placeholder="e.g., Armoured Cable 4X16Mm or Cable Lug 5.5 Yellow", key="lookup_name")
    with col_b:
        lookup_type = st.text_input("Type (opt)", placeholder="Electrical", key="lookup_type")
    
    col_c, col_d = st.columns(2)
    with col_c: lookup_sub = st.text_input("SubType (opt)", placeholder="Cable", key="lookup_sub")
    with col_d: lookup_uom = st.text_input("UOM (opt)", placeholder="MTR", key="lookup_uom")
    
    if st.button("🔍 Standardize Now", type="primary", use_container_width=True):
        if lookup_name:
            with st.spinner("Standardizing..."):
                result = engine.lookup_single(lookup_name, lookup_type, lookup_sub, lookup_uom if lookup_uom else "NOS")
                st.session_state.lookup_result = result
            
            if result:
                st.success(f"✅ Confidence: {result.get('Confidence', 'N/A')}%")
                result_df = pd.DataFrame([
                    {"Field": "Material_ID", "Value": result.get('Material_ID', '')},
                    {"Field": "Standardized Material_Type", "Value": result.get('Standardized Material_Type', '')},
                    {"Field": "Standardized Material_Subtype", "Value": result.get('Standardized Material_Subtype', '')},
                    {"Field": "Standardized Material_Name", "Value": result.get('Standardized Material_Name', '')},
                    {"Field": "Material_Code", "Value": result.get('Material_Code', '')},
                    {"Field": "UOM", "Value": result.get('UOM', '')},
                    {"Field": "HSN_Code", "Value": result.get('HSN_Code', '')},
                    {"Field": "Status", "Value": result.get('Status', 'Active')},
                ])
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                
                st.code(f"{result.get('Standardized Material_Name', '')} | HSN: {result.get('HSN_Code', '')} | UOM: {result.get('UOM', '')}", language="text")
        else:
            st.warning("Enter a material name")
    
    with st.expander("📝 Examples"):
        st.markdown("""
        | Input | Output | HSN |
        |-------|--------|-----|
        | Armoured Cable 4X16Mm | CABLE-ARM-4C-16MM | 8544 |
        | Cable Lugs 5.5 -250 Yellow | LUG-CU-5.5-RING-YELLOW | 8536 |
        | Ball Bearing 6206 ZZ | BEARING-6206 | 8482 |
        | Toyota Camry BDG934BQ | VEHICLE-SEDAN-TOYOTA-CAMRY-BDG934BQ | 8703 |
        """)

# ================================================================
# TAB 1: BATCH PROCESS
# ================================================================
with tab1:
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 📤 Upload File for Batch Processing")
        st.caption("Excel (.xlsx, .xls) or CSV")
        
        if "Convert" in mode:
            st.info("⚡ **Fast Convert Mode**: For already-standardized files. Assigns HSN codes + converts to ERP format.")
        else:
            st.info("🧠 **AI Standardize Mode**: For raw/unstandardized files. AI-powered standardization from scratch.")
        
        uploaded_file = st.file_uploader("Choose file", type=['xlsx', 'xls', 'csv'], key="file_upload")
    
    with col_right:
        st.markdown("### 📋 Expected Columns")
        if "Convert" in mode:
            st.caption("Standardized_Name, Category, Sub-Category, UOM")
        else:
            st.caption("MaterialName, MaterialType, MaterialSubType, UOM, MaterialCode")
    
    if uploaded_file:
        st.markdown("---")
        try:
            preview_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.markdown(f"#### Preview: {uploaded_file.name}")
            st.dataframe(preview_df.head(10), use_container_width=True)
            st.caption(f"Rows: {len(preview_df)} | Columns: {list(preview_df.columns)}")
        except Exception as e:
            st.error(f"Error: {e}")
            preview_df = None
        
        st.markdown("---")
        
        btn_label = "⚡ Convert & Assign HSN" if "Convert" in mode else "🧠 AI Standardize"
        
        if st.button(btn_label, type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="Starting...")
            status_text = st.empty()
            
            try:
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                def update(pct, msg): progress_bar.progress(pct, text=msg)
                engine.set_progress_callback(update)
                
                mat_df, ast_df, dup_df, _ = engine.process_file(tmp_path)
                
                progress_bar.progress(100, text="Complete!")
                st.session_state.materials_df = mat_df
                st.session_state.assets_df = ast_df
                st.session_state.duplicates_df = dup_df
                st.session_state.processed = True
                
                try: os.unlink(tmp_path)
                except: pass
                
                status_text.empty()
                st.success("✅ Complete!")
                st.balloons()
                
                m = len(mat_df) if mat_df is not None else 0
                a = len(ast_df) if ast_df is not None else 0
                d = len(dup_df) if dup_df is not None and len(dup_df) > 0 else 0
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Rows", m + a)
                c2.metric("Quality", f"{engine.quality_score}%")
                if d > 0: c3.metric("Duplicates", d, delta=f"⚠️ {d}")
                else: c3.metric("Duplicates", 0)
                
                st.info("Go to Results tab →")
                
            except Exception as e:
                progress_bar.empty(); status_text.empty()
                st.error(f"Error: {e}")

# ================================================================
# TAB 2: RESULTS
# ================================================================
with tab2:
    if not st.session_state.processed:
        st.info("Process a file first")
    else:
        st.markdown("### 📊 Results")
        
        m_count = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a_count = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        d_count = len(st.session_state.duplicates_df) if st.session_state.duplicates_df is not None else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Materials", m_count)
        c2.metric("Assets", a_count)
        c3.metric("Duplicates", d_count)
        
        st.markdown("---")
        
        if m_count > 0:
            st.subheader("📦 Standardized Data")
            st.dataframe(st.session_state.materials_df, use_container_width=True, hide_index=True)
            
            col_x1, col_x2, col_x3, col_x4 = st.columns(4)
            with col_x1:
                buf = BytesIO(); st.session_state.materials_df.to_excel(buf, index=False)
                st.download_button("📥 Excel", buf.getvalue(), f"materials_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)
            with col_x2:
                csv = st.session_state.materials_df.to_csv(index=False)
                st.download_button("📥 CSV", csv, f"materials_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            with col_x3:
                js = engine.export_to_json(st.session_state.materials_df)
                st.download_button("📥 JSON", js, f"materials_{datetime.now().strftime('%Y%m%d')}.json", "application/json", use_container_width=True)
            with col_x4:
                sql = engine.export_to_sql(st.session_state.materials_df)
                st.download_button("📥 SQL", sql, f"materials_{datetime.now().strftime('%Y%m%d')}.sql", "text/plain", use_container_width=True)
        
        if a_count > 0:
            st.markdown("---")
            st.subheader("🏢 Assets")
            st.dataframe(st.session_state.assets_df, use_container_width=True, hide_index=True)
            buf = BytesIO(); st.session_state.assets_df.to_excel(buf, index=False)
            st.download_button("📥 Download Assets", buf.getvalue(), "assets.xlsx", use_container_width=True)
        
        if d_count > 0:
            st.markdown("---")
            st.warning(f"⚠️ {d_count} Duplicates Found")
            st.dataframe(st.session_state.duplicates_df, use_container_width=True, hide_index=True)

# ================================================================
# TAB 3: HELP
# ================================================================
with tab3:
    st.markdown("""
    ## 🏗️ Enterprise Material Standardization Engine
    
    ### Features
    - **Quick Lookup** - Single item instant standardization
    - **Batch Processing** - Process thousands of rows
    - **Duplicate Detection** - Find and flag duplicates
    - **Quality Scoring** - Data health metrics
    - **Multi-Format Export** - Excel, CSV, JSON, SQL
    
    ### Modes
    | Mode | Use Case | Speed |
    |------|----------|-------|
    | Convert + HSN | Already standardized, need HSN | Seconds |
    | AI Standardize | Raw/unstandardized data | Minutes |
    
    ### Output Format
    | Column | Example |
    |--------|---------|
    | Material_ID | MAT-00001 |
    | Standardized Material_Type | CABLE |
    | Standardized Material_Name | CABLE-ARM-4C-16MM |
    | HSN_Code | 8544 |
    | UOM | METER |
    
    ### Standards: ISO 8000 | ECLASS | UNSPSC | IEC 61360 | HSN
    """)

st.markdown("---")
st.caption("Enterprise Material Standardization Engine v4.0 | Fortune 500 Grade | Churchgate Group")
