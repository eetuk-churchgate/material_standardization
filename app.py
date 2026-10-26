"""
FORTUNE 500 AI MATERIAL & ASSET STANDARDIZATION ENGINE (MERGED VERSION)
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
import re
import yaml
import pickle
from datetime import datetime
from io import BytesIO
from rapidfuzz import fuzz, process
from llm_handler import LLMHandler

# ================================================================
# ENGINE CLASS (MERGED TO FIX IMPORT ERROR)
# ================================================================
class MaterialAIEngine:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.llm = LLMHandler(config_path)
        self.master_df = None
        self.master_names = []
        self.mat_counter = 1
        self.ast_counter = 1
        self.materials = []
        self.assets = []
        self.audit = []
        self.review = []
        self.duplicates_found = []
        self.hsn_map = self.config.get('hsn_codes', {})
        self.uom_map = self.config.get('uom_mapping', {})
        self.llm_calls = 0
        self.fast_calls = 0
        self.progress_callback = None
        self.batch_size = 100
        self.master_file_path = "data/master_data.pkl"
        self.mode = "convert"
        self.processing_history = []
        self.quality_score = 0
        
        self._auto_load_master()
        print(f"🚀 Engine Ready | Mode: {self.mode} | LLM: {self.llm.get_provider_name()}")
    
    def set_mode(self, mode): self.mode = mode
    def _auto_load_master(self):
        if Path(self.master_file_path).exists():
            try: self.load_master_data()
            except: pass
    def set_progress_callback(self, callback): self.progress_callback = callback
    
    def learn_from_master(self, file_path):
        try: df = pd.read_excel(file_path)
        except: df = pd.concat([pd.read_excel(file_path, sheet_name=s) for s in pd.ExcelFile(file_path).sheet_names], ignore_index=True)
        if self.master_df is None: self.master_df = df
        else: self.master_df = pd.concat([self.master_df, df], ignore_index=True)
        new_names = []
        for col in ['Standardized_Name', 'Standardized_Asset_Name', 'MaterialName']:
            if col in df.columns:
                new_names = df[col].dropna().astype(str).str.upper().str.strip().tolist()
                break
        before = len(self.master_names)
        self.master_names.extend(new_names)
        self.master_names = list(set([n for n in self.master_names if n and len(n) > 2]))
        self.save_master_data()
        return len(self.master_names) - before
    
    def save_master_data(self, filepath=None):
        if filepath is None: filepath = self.master_file_path
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump({'master_names': self.master_names, 'master_df': self.master_df.to_dict() if self.master_df is not None else None}, f)
    
    def load_master_data(self, filepath=None):
        if filepath is None: filepath = self.master_file_path
        if Path(filepath).exists():
            with open(filepath, 'rb') as f: data = pickle.load(f)
            self.master_names = data.get('master_names', [])
            if data.get('master_df'): self.master_df = pd.DataFrame.from_dict(data['master_df'])
            return True
        return False
    
    def clear_master_data(self):
        self.master_names = []
        self.master_df = None
        if Path(self.master_file_path).exists(): os.remove(self.master_file_path)
    
    def process_file(self, file_path):
        df = pd.read_excel(file_path) if not str(file_path).endswith('.csv') else pd.read_csv(file_path)
        if self.mode == "convert": return self._process_convert(df)
        else: return self._process_standardize(df)
    
    def lookup_single(self, name, mat_type="", sub_type="", uom="NOS"):
        name_upper = str(name).strip().upper()
        if name_upper in self.master_names: return self._build_lookup_result(name_upper, mat_type, sub_type, uom, 100, 'exact')
        if self.master_names:
            best = process.extractOne(name_upper, self.master_names, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 85: return self._build_lookup_result(best[0], mat_type, sub_type, uom, best[1], 'fuzzy')
        is_asset = self._is_asset(name_upper, mat_type)
        if self.llm.is_available():
            llm_res = self.llm.standardize(name_upper, mat_type, sub_type, uom, is_asset)
            if llm_res:
                return {'Material_ID': 'LOOKUP', 'Standardized Material_Type': llm_res.get('asset_type', '') if is_asset else llm_res.get('material_type', ''), 'Standardized Material_Subtype': llm_res.get('asset_subtype', '') if is_asset else llm_res.get('material_subtype', ''), 'Standardized Material_Name': llm_res.get('standardized_name', ''), 'Material_Code': '', 'UOM': llm_res.get('uom', uom) if not is_asset else 'UNIT', 'HSN_Code': llm_res.get('hsn_code', ''), 'Status': 'Active', 'Confidence': llm_res.get('confidence', 95)}
        return self._build_lookup_result(name_upper, mat_type, sub_type, uom, 60, 'rule_based')
    
    def _build_lookup_result(self, name, mat_type, sub_type, uom, confidence, source):
        hsn = self._get_hsn(f"{mat_type} {name}")
        std_uom = self.uom_map.get(uom.upper(), uom.upper())
        parts = [p for p in [mat_type.upper().replace(' ', '-'), sub_type.upper().replace(' ', '-'), self._extract_size(name)] if p]
        std_name = re.sub(r'-+', '-', '-'.join(parts)) if parts else self._clean(name)
        return {'Material_ID': 'LOOKUP', 'Standardized Material_Type': mat_type.upper() if mat_type else self._guess_type(name), 'Standardized Material_Subtype': sub_type.upper() if sub_type else '', 'Standardized Material_Name': std_name, 'Material_Code': '', 'UOM': std_uom, 'HSN_Code': hsn, 'Status': 'Active', 'Confidence': confidence, 'Source': source}
    
    def _process_convert(self, df):
        self.mat_counter = 1; self.ast_counter = 1; self.duplicates_found = []; results = []; seen = {}
        for idx, row in df.iterrows():
            res = self._convert_row(row)
            if res:
                std_name = res.get('Standardized Material_Name', '')
                if std_name in seen: self.duplicates_found.append({'name': std_name, 'first_row': seen[std_name], 'duplicate_row': idx + 2})
                else: seen[std_name] = idx + 2
                results.append(res)
            if (idx + 1) % 1000 == 0 and self.progress_callback: self.progress_callback(int((idx + 1) / len(df) * 100), f"Converting: {idx+1}/{len(df)}")
        if self.progress_callback: self.progress_callback(100, "Complete!")
        out_df = pd.DataFrame(results)
        self.quality_score = round((out_df['HSN_Code'].notna().sum() / len(out_df)) * 100) if len(out_df) > 0 else 0
        return out_df, pd.DataFrame(), pd.DataFrame(self.duplicates_found), pd.DataFrame()
    
    def _process_standardize(self, df):
        self.mat_counter = 1; self.ast_counter = 1; self.materials = []; self.assets = []; self.llm_calls = 0; self.fast_calls = 0
        for idx, row in df.iterrows():
            res = self._standardize_row(row)
            if res:
                if res.get('is_asset'): self.assets.append(res)
                else: self.materials.append(res)
            if (idx + 1) % 50 == 0 and self.progress_callback: self.progress_callback(int((idx + 1) / len(df) * 100), f"Processed: {idx+1}/{len(df)} | AI: {self.llm_calls}")
        if self.progress_callback: self.progress_callback(100, "Complete!")
        self.quality_score = round((self.fast_calls / max(len(df), 1)) * 100)
        return pd.DataFrame(self.materials), pd.DataFrame(self.assets), pd.DataFrame(), pd.DataFrame()

    def _standardize_row(self, row):
        old_name = self._field(row, ['MaterialName', 'Material_Name', 'Name', 'Description'])
        mat_type = self._field(row, ['MaterialType', 'Material_Type', 'Type', 'Category'])
        sub_type = self._field(row, ['MaterialSubType', 'Material_Subtype', 'SubType'])
        uom = self._field(row, ['UOM', 'Unit', 'UnitOfMeasure'])
        old_code = self._field(row, ['MaterialCode', 'Material_Code', 'Code', 'ID', 'Id'])
        if not old_name: return None
        name_upper = str(old_name).upper().strip()
        if name_upper in self.master_names: self.fast_calls += 1; return self._build_result(name_upper, old_code, uom, 100, 'exact_match')
        if self.master_names:
            best = process.extractOne(name_upper, self.master_names, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 90: self.fast_calls += 1; return self._build_result(best[0], old_code, uom, best[1], 'fuzzy_match')
        is_asset = self._is_asset(name_upper, mat_type)
        if self.llm.is_available():
            self.llm_calls += 1
            llm_result = self.llm.standardize(name_upper, mat_type, sub_type, uom, is_asset)
            if llm_result: return self._format_llm_result(llm_result, name_upper, old_code, uom, is_asset)
        self.fast_calls += 1
        return self._rule_based(name_upper, mat_type, sub_type, uom, old_code, is_asset)

    def _convert_row(self, row):
        std_name = self._field(row, ['Standardized_Name', 'Standardized Material_Name', 'Material_Name'])
        category = self._field(row, ['Category', 'Material_Type', 'MaterialType'])
        subcategory = self._field(row, ['Sub-Category', 'Material_Subtype', 'MaterialSubType'])
        material_code = self._field(row, ['Material_Code', 'MaterialCode', 'Code', 'ID'])
        uom = self._field(row, ['UOM', 'Unit'])
        existing_hsn = self._field(row, ['HSN_Code', 'HSNCode', 'HSN'])
        if not std_name: std_name = "UNKNOWN"
        hsn = str(existing_hsn).strip() if existing_hsn and len(str(existing_hsn).strip()) >= 4 else self._get_hsn(f"{category} {subcategory} {std_name}")
        std_uom = self.uom_map.get(str(uom).upper().strip(), str(uom).upper().strip()) if uom else "UNIT"
        if self._is_asset(str(std_name), str(category)): std_id = f"AST-{self.ast_counter:05d}"; self.ast_counter += 1
        else: std_id = f"MAT-{self.mat_counter:05d}"; self.mat_counter += 1
        return {'Material_ID': std_id, 'Standardized Material_Type': str(category).upper() if category else self._guess_type(std_name), 'Standardized Material_Subtype': str(subcategory).upper() if subcategory else '', 'Standardized Material_Name': str(std_name).upper(), 'Material_Code': str(material_code) if material_code else '', 'UOM': std_uom, 'HSN_Code': hsn, 'Status': 'Active'}

    def _format_llm_result(self, llm_res, name, code, uom, is_asset):
        std_uom = self.uom_map.get(str(uom).upper(), str(uom).upper())
        std_id = f"AST-{self.ast_counter:05d}" if is_asset else f"MAT-{self.mat_counter:05d}"
        if is_asset: self.ast_counter += 1
        else: self.mat_counter += 1
        return {'Material_ID': std_id, 'Standardized Material_Type': llm_res.get('asset_type', '') if is_asset else llm_res.get('material_type', ''), 'Standardized Material_Subtype': llm_res.get('asset_subtype', '') if is_asset else llm_res.get('material_subtype', ''), 'Standardized Material_Name': llm_res.get('standardized_name', ''), 'Material_Code': code, 'UOM': llm_res.get('uom', std_uom) if not is_asset else 'UNIT', 'HSN_Code': llm_res.get('hsn_code', ''), 'Status': 'Active', 'Confidence_Score': llm_res.get('confidence', 95), 'Original_Name': name, 'Source': 'llm_groq', 'is_asset': is_asset}

    def _build_result(self, std_name, code, uom, conf, source):
        std_id = f"MAT-{self.mat_counter:05d}"; self.mat_counter += 1
        return {'Material_ID': std_id, 'Standardized Material_Type': '', 'Standardized Material_Subtype': '', 'Standardized Material_Name': std_name, 'Material_Code': code, 'UOM': uom, 'HSN_Code': self._get_hsn(std_name), 'Status': 'Active', 'Confidence_Score': conf, 'Original_Name': std_name, 'Source': source, 'is_asset': False}
        
    def _rule_based(self, name, mat_type, sub_type, uom, old_code, is_asset):
        if is_asset: return self._make_asset(name, f"{mat_type.upper()}-{self._clean(name)}", mat_type, sub_type, '8479', old_code, 60)
        size = self._extract_size(name)
        std_name = f"{mat_type.upper()}-{sub_type.upper()}-{size}".strip("-") if size else self._clean(name)
        std_id = f"MAT-{self.mat_counter:05d}"; self.mat_counter += 1
        return {'Material_ID': std_id, 'Standardized Material_Type': mat_type.upper(), 'Standardized Material_Subtype': sub_type.upper(), 'Standardized Material_Name': std_name, 'Material_Code': old_code, 'UOM': self.uom_map.get(uom.upper(), uom.upper()), 'HSN_Code': self._get_hsn(name), 'Status': 'Active', 'Confidence_Score': 60, 'Original_Name': name, 'Source': 'rule_based', 'is_asset': False}

    def _make_asset(self, orig, std_name, atype, subtype, hsn, code, conf):
        std_id = f"AST-{self.ast_counter:05d}"; self.ast_counter += 1
        return {'Material_ID': std_id, 'Standardized Material_Type': atype, 'Standardized Material_Subtype': subtype, 'Standardized Material_Name': std_name, 'Material_Code': code, 'UOM': 'UNIT', 'HSN_Code': hsn, 'Status': 'Active', 'Confidence_Score': conf, 'Original_Name': orig, 'Source': 'rule_based', 'is_asset': True}
                
    def _field(self, row, names):
        for n in names:
            if n in row.index and pd.notna(row[n]) and str(row[n]).strip(): return row[n]
        return ""
    def _is_asset(self, name, mat_type):
        combined = f"{name} {mat_type}".upper()
        return any(kw in combined for kw in ['VEHICLE','GENERATOR','COMPRESSOR','CHILLER','ELEVATOR','LIFT','PUMP','COMPUTER','LAPTOP','SERVER','AC']) or bool(re.search(r'[A-Z]{3}\d{2,3}[A-Z]{2}', name))
    def _clean(self, text): return re.sub(r'-+', '-', re.sub(r'\s+', '-', re.sub(r'[^\w\s\-]', '', str(text).upper()))).strip('-')
    def _extract_size(self, name):
        m = re.search(r'(\d+)\s*[C]\s*[Xx]\s*(\d+\.?\d*)\s*(MM|SQMM)?', name)
        if m: return f"{m.group(1)}C-{m.group(2)}{m.group(3) or 'MM'}"
        m = re.search(r'(\d+)\s*(MM|INCH|A|W)', name)
        if m: return f"{m.group(1)}{m.group(2)}"
        return ""
    def _get_hsn(self, text):
        t = str(text).upper()
        rules = [(['CABLE'], '8544'), (['BREAKER', 'MCB'], '8536'), (['LUG', 'GLAND'], '8536'), (['LED', 'LIGHT'], '9405'), (['BEARING'], '8482'), (['FILTER'], '8421'), (['PUMP'], '8413'), (['PIPE', 'TEE', 'ELBOW'], '7306'), (['VALVE'], '8481'), (['VEHICLE', 'CAR'], '8703'), (['GENERATOR'], '8502'), (['COMPUTER'], '8471')]
        for kws, hsn in rules:
            if any(k in t for k in kws): return hsn
        return '8479'
    def _guess_type(self, name):
        t = str(name).upper()
        for typ, kws in {'CABLE':['CABLE'], 'LUG':['LUG'], 'BEARING':['BEARING'], 'PUMP':['PUMP'], 'PIPE':['PIPE'], 'VALVE':['VALVE'], 'VEHICLE':['CAR','VEHICLE']}.items():
            if any(k in t for k in kws): return typ
        return 'UNKNOWN'
    def export_to_json(self, df): return df.to_json(orient='records', indent=2) if df is not None else "[]"
    def get_quality_report(self): return {'quality_score': self.quality_score, 'duplicates_found': len(self.duplicates_found), 'llm_provider': self.llm.get_provider_name()}

# ================================================================
# APP UI
# ================================================================
st.set_page_config(page_title="Enterprise Material Engine", page_icon="🏗️", layout="wide")

if 'engine' not in st.session_state:
    st.session_state.engine = MaterialAIEngine()
    st.session_state.master_loaded = len(st.session_state.engine.master_names) > 0
if 'materials_df' not in st.session_state: st.session_state.materials_df = None
if 'assets_df' not in st.session_state: st.session_state.assets_df = None
if 'duplicates_df' not in st.session_state: st.session_state.duplicates_df = None
if 'processed' not in st.session_state: st.session_state.processed = False

engine = st.session_state.engine

with st.sidebar:
    st.title("🏗️ Enterprise Engine")
    if st.session_state.processed:
        st.metric("Data Quality", f"{engine.get_quality_report()['quality_score']}%")
    st.markdown("---")
    st.subheader("⚡ Processing Mode")
    mode = st.radio("Choose mode:", ["Convert Format + HSN (Fast)", "AI Standardize (Smart)"], index=0)
    engine.set_mode("convert" if "Convert" in mode else "standardize")
    st.markdown("---")
    llm_name = engine.llm.get_provider_name()
    if llm_name == 'groq': st.success("🟢 Groq LLM")
    elif llm_name == 'openai': st.success("🔵 OpenAI LLM")
    else: st.warning("🟡 Rule-Based")
    st.markdown("---")
    with st.expander("🔑 API Keys"):
        groq_key = st.text_input("Groq Key", type="password", value=os.getenv("GROQ_API_KEY", ""))
        if groq_key: os.environ["GROQ_API_KEY"] = groq_key
        if st.button("Reconnect"): st.session_state.engine = MaterialAIEngine(); st.rerun()
    st.markdown("---")
    if "AI" in mode:
        st.subheader("📚 Master Data")
        master_file = st.file_uploader("Upload Master", type=['xlsx', 'xls'], key="master")
        if master_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp: tmp.write(master_file.getvalue())
            count = engine.learn_from_master(tmp.name)
            if count: st.session_state.master_loaded = True; st.success(f"+{count} names")
        if st.session_state.master_loaded:
            st.info(f"📊 {len(engine.master_names)} names")
            if st.button("Clear Master"): engine.clear_master_data(); st.session_state.master_loaded = False; st.rerun()
    st.caption("v5.0 Enterprise | Churchgate Group")

st.title("🏗️ Enterprise Material Standardization")
st.markdown("### Fortune 500 Grade | AI-Powered | Audit Ready")

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1: st.info("⚡ Fast Convert" if "Convert" in mode else "🧠 AI Mode")
with col_s2: st.info(f"📚 Master: {len(engine.master_names)}")
with col_s3: st.info("🌍 ISO 8000 + HSN")
with col_s4: 
    if st.session_state.processed: st.metric("Quality", f"{engine.quality_score}%")

st.markdown("---")
tab0, tab1, tab2, tab3 = st.tabs(["🔍 Quick Lookup", "📤 Batch Process", "📊 Results", "ℹ️ Help"])

with tab0:
    st.markdown("### 🔍 Single Item Standardization")
    lookup_name = st.text_input("Material Name", placeholder="e.g. Cable Lug 5.5 Yellow", key="lookup_name")
    if st.button("🔍 Standardize Now", type="primary"):
        if lookup_name:
            with st.spinner("Standardizing..."):
                result = engine.lookup_single(lookup_name)
            if result:
                st.success(f"✅ Confidence: {result.get('Confidence', 'N/A')}%")
                st.dataframe(pd.DataFrame([result]).T, use_container_width=True)
                st.code(f"{result.get('Standardized Material_Name', '')} | HSN: {result.get('HSN_Code', '')}", language="text")

with tab1:
    st.markdown("### 📤 Upload File")
    uploaded_file = st.file_uploader("Choose file", type=['xlsx', 'xls', 'csv'], key="file_upload")
    if uploaded_file:
        if st.button("Process File", type="primary"):
            progress_bar = st.progress(0, text="Starting...")
            status_text = st.empty()
            try:
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue()); tmp_path = tmp.name
                def update(pct, msg): progress_bar.progress(pct, text=msg)
                engine.set_progress_callback(update)
                mat_df, ast_df, dup_df, _ = engine.process_file(tmp_path)
                progress_bar.progress(100, text="Complete!")
                st.session_state.materials_df = mat_df; st.session_state.assets_df = ast_df; st.session_state.duplicates_df = dup_df; st.session_state.processed = True
                try: os.unlink(tmp_path)
                except: pass
                status_text.empty(); st.success("✅ Complete!"); st.balloons()
            except Exception as e:
                progress_bar.empty(); status_text.empty(); st.error(f"Error: {e}")

with tab2:
    if not st.session_state.processed: st.info("Process a file first")
    else:
        st.markdown("### 📊 Results")
        m_count = len(st.session_state.materials_df) if st.session_state.materials_df is not None else 0
        a_count = len(st.session_state.assets_df) if st.session_state.assets_df is not None else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Materials", m_count); c2.metric("Assets", a_count); c3.metric("Quality", f"{engine.quality_score}%")
        
        if m_count > 0:
            st.dataframe(st.session_state.materials_df, use_container_width=True)
            buf = BytesIO(); st.session_state.materials_df.to_excel(buf, index=False)
            st.download_button("📥 Download Excel", buf.getvalue(), "materials.xlsx", use_container_width=True)
        if a_count > 0:
            st.subheader("🏢 Assets")
            st.dataframe(st.session_state.assets_df, use_container_width=True)

with tab3:
    st.markdown("### Help & Standards")
    st.markdown("ISO 8000 | ECLASS | UNSPSC | IEC 61360 | HSN")

st.caption("Enterprise Material Standardization Engine v5.0 | Churchgate Group")