"""
CORE AI ENGINE - Smart Hybrid with Batch Processing + Persistent Master Data
Master match first (fast) -> Rule-based (fast) -> LLM only when needed
Learns from any master format, auto-assigns HSN codes
Saves/Loads master data to/from disk for persistence
"""
import pandas as pd
import numpy as np
from pathlib import Path
import re
import yaml
import pickle
import os
from rapidfuzz import fuzz, process

from llm_handler import LLMHandler

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
        self.hsn_map = self.config.get('hsn_codes', {})
        self.llm_calls = 0
        self.fast_calls = 0
        self.progress_callback = None
        self.batch_size = 500
        self.master_file_path = "data/master_data.pkl"
        
        # Auto-load saved master data on startup
        self._auto_load_master()
        
        print(f"Engine ready | LLM: {self.llm.get_provider_name()} | Master: {len(self.master_names)} names | Batch: {self.batch_size}")
    
    def _auto_load_master(self):
        """Load master data from disk if exists"""
        if Path(self.master_file_path).exists():
            try:
                self.load_master_data()
                print(f"Auto-loaded {len(self.master_names)} master names from disk")
            except Exception as e:
                print(f"Could not auto-load master: {e}")
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def learn_from_master(self, file_path):
        """Learn from any master Excel format"""
        print(f"Learning from: {file_path}")
        try:
            df = pd.read_excel(file_path)
        except:
            xl = pd.ExcelFile(file_path)
            dfs = [pd.read_excel(file_path, sheet_name=s) for s in xl.sheet_names]
            df = pd.concat(dfs, ignore_index=True)
        
        if self.master_df is None:
            self.master_df = df
        else:
            self.master_df = pd.concat([self.master_df, df], ignore_index=True)
        
        name_columns = [
            'Standardized_Name', 'Standardized_Asset_Name', 'Standardized_Material_Name',
            'Standardized Material_Name', 'Standardized Material Name',
            'MaterialName', 'Material_Name', 'Material Name',
            'Standardized Name', 'StandardizedName'
        ]
        
        found = False
        new_names = []
        for col in name_columns:
            if col in df.columns:
                new_names = df[col].dropna().astype(str).str.upper().str.strip().tolist()
                print(f"Found names in column: '{col}'")
                found = True
                break
        
        if not found:
            print(f"Available columns: {list(df.columns)}")
            for col in df.columns:
                if df[col].dtype == 'object':
                    new_names.extend(df[col].dropna().astype(str).str.upper().str.strip().tolist())
        
        # Add new names (avoid duplicates)
        before_count = len(self.master_names)
        self.master_names.extend(new_names)
        self.master_names = list(set([n for n in self.master_names if n and len(n) > 2]))
        after_count = len(self.master_names)
        added = after_count - before_count
        
        # Auto-save to disk
        self.save_master_data()
        
        print(f"Added {added} new names. Total: {after_count}")
        return added
    
    def save_master_data(self, filepath=None):
        """Save master data to disk"""
        if filepath is None:
            filepath = self.master_file_path
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'master_names': self.master_names,
            'master_df': self.master_df.to_dict() if self.master_df is not None else None
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"Saved {len(self.master_names)} names to {filepath}")
    
    def load_master_data(self, filepath=None):
        """Load master data from disk"""
        if filepath is None:
            filepath = self.master_file_path
        
        if Path(filepath).exists():
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            self.master_names = data.get('master_names', [])
            df_dict = data.get('master_df')
            if df_dict:
                self.master_df = pd.DataFrame.from_dict(df_dict)
            print(f"Loaded {len(self.master_names)} names from {filepath}")
            return True
        return False
    
    def clear_master_data(self):
        """Clear all master data and delete saved file"""
        self.master_names = []
        self.master_df = None
        if Path(self.master_file_path).exists():
            os.remove(self.master_file_path)
        print("Master data cleared")
    
    def process_file(self, file_path):
        """Process uploaded file in batches"""
        print(f"Processing: {Path(file_path).name}")
        
        df = self._read_file(file_path)
        if df is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        total = len(df)
        print(f"Total rows: {total} | Batch size: {self.batch_size} | Master names: {len(self.master_names)}")
        
        self.mat_counter = 1
        self.ast_counter = 1
        self.materials = []
        self.assets = []
        self.audit = []
        self.review = []
        self.llm_calls = 0
        self.fast_calls = 0
        
        num_batches = (total + self.batch_size - 1) // self.batch_size
        
        for batch_num in range(num_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, total)
            batch = df.iloc[start_idx:end_idx]
            
            for idx, row in batch.iterrows():
                result = self._process_row(row)
                if result:
                    if result.get('is_asset'):
                        self.assets.append(result)
                    else:
                        self.materials.append(result)
            
            progress_pct = int((end_idx / total) * 100)
            if self.progress_callback:
                self.progress_callback(progress_pct, f"Batch {batch_num+1}/{num_batches} | LLM: {self.llm_calls} | Fast: {self.fast_calls}")
            
            print(f"Batch {batch_num+1}/{num_batches} | Rows: {end_idx}/{total} | LLM: {self.llm_calls} | Fast: {self.fast_calls}")
        
        print(f"DONE | Total: {total} | LLM: {self.llm_calls} | Fast: {self.fast_calls} | Materials: {len(self.materials)} | Assets: {len(self.assets)}")
        
        mat_df = pd.DataFrame(self.materials) if self.materials else pd.DataFrame()
        ast_df = pd.DataFrame(self.assets) if self.assets else pd.DataFrame()
        aud_df = pd.DataFrame(self.audit) if self.audit else pd.DataFrame()
        rev_df = pd.DataFrame(self.review) if self.review else pd.DataFrame()
        
        return mat_df, ast_df, aud_df, rev_df
    
    def _read_file(self, path):
        """Read Excel or CSV"""
        try:
            if str(path).endswith('.csv'):
                return pd.read_csv(path)
            return pd.read_excel(path)
        except Exception as e:
            print(f"Error reading file: {e}")
        return None
    
    def _process_row(self, row):
        """Process single row through smart hybrid pipeline"""
        old_name = self._field(row, ['MaterialName', 'Material_Name', 'Name', 'Description'])
        mat_type = self._field(row, ['MaterialType', 'Material_Type', 'Type', 'Category'])
        sub_type = self._field(row, ['MaterialSubType', 'Material_Subtype', 'SubType', 'Sub_Type'])
        uom = self._field(row, ['UOM', 'Unit', 'UnitOfMeasure', 'Unit_Of_Measure'])
        old_code = self._field(row, ['MaterialCode', 'Material_Code', 'Code', 'ID', 'Id'])
        
        if not old_name:
            return None
        
        old_name = str(old_name).strip()
        mat_type = str(mat_type).strip() if mat_type and pd.notna(mat_type) else ""
        sub_type = str(sub_type).strip() if sub_type and pd.notna(sub_type) else ""
        uom = str(uom).strip() if uom and pd.notna(uom) else "NOS"
        old_code = str(old_code).strip() if old_code and pd.notna(old_code) else ""
        name_upper = old_name.upper()
        
        # LAYER 1: Exact master match
        if name_upper in self.master_names:
            self.fast_calls += 1
            return self._build_material(name_upper, old_code, uom, 100, 'exact_match')
        
        # LAYER 2: Fuzzy master match (threshold 85%)
        if self.master_names:
            best = process.extractOne(name_upper, self.master_names, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 85:
                self.fast_calls += 1
                return self._build_material(best[0], old_code, uom, best[1], 'fuzzy_match')
        
        # LAYER 3: Rule-based (always works, fast)
        is_asset = self._is_asset(name_upper, mat_type)
        rule_result = self._rule_based(name_upper, mat_type, sub_type, uom, old_code, is_asset)
        
        # LAYER 4: LLM enhancement for low-confidence items
        if self.llm.is_available() and rule_result.get('Confidence_Score', 0) < 80:
            self.llm_calls += 1
            llm_result = self.llm.standardize(old_name, mat_type, sub_type, uom, is_asset)
            if llm_result:
                return self._format_llm(llm_result, old_name, old_code, uom, is_asset)
        
        self.fast_calls += 1
        return rule_result
    
    def _field(self, row, names):
        """Extract field from row using multiple possible column names"""
        for n in names:
            if n in row.index and pd.notna(row[n]) and str(row[n]).strip():
                return row[n]
        return ""
    
    def _build_material(self, std_name, old_code, uom, confidence, source):
        """Build material result from master match"""
        std_uom = self.config['uom_mapping'].get(uom.upper(), uom.upper())
        hsn = self._get_hsn('', std_name)
        
        std_id = f"MAT-{self.mat_counter:05d}"
        self.mat_counter += 1
        
        result = {
            'Standardized_ID': std_id,
            'Standardized_Name': std_name,
            'Material_Type': '',
            'Material_Subtype': '',
            'Material_Code': old_code,
            'UOM': std_uom,
            'HSN_Code': hsn,
            'Status': 'Active',
            'Confidence_Score': confidence,
            'Original_Name': std_name,
            'Source': source,
            'is_asset': False
        }
        
        # Try to enrich from master dataframe
        if self.master_df is not None:
            for col in ['Material_Type', 'Material_Subtype', 'Asset_Type', 'Asset_Subtype', 'HSN_Code']:
                master_col = None
                for mc in [col, col.replace('_', ' '), col.replace('_', '')]:
                    if mc in self.master_df.columns:
                        master_col = mc
                        break
                if master_col:
                    match_row = self.master_df[self.master_df.apply(
                        lambda r: str(r[master_col]).upper() if pd.notna(r[master_col]) else '', axis=1
                    ) == std_name]
                    if len(match_row) > 0 and pd.notna(match_row.iloc[0][master_col]):
                        result[col] = match_row.iloc[0][master_col]
        
        return result
    
    def _format_llm(self, llm_result, old_name, old_code, uom, is_asset):
        """Format LLM response into standard output"""
        std_uom = self.config['uom_mapping'].get(uom.upper(), uom.upper())
        
        if is_asset:
            std_id = f"AST-{self.ast_counter:05d}"
            self.ast_counter += 1
            return {
                'Standardized_ID': std_id,
                'Standardized_Asset_Name': llm_result.get('standardized_name', ''),
                'Asset_Type': llm_result.get('asset_type', ''),
                'Asset_Subtype': llm_result.get('asset_subtype', ''),
                'Old_Code': old_code,
                'UOM': 'UNIT',
                'HSN_Code': llm_result.get('hsn_code', ''),
                'Status': 'Active',
                'Confidence_Score': llm_result.get('confidence', 85),
                'Original_Name': old_name,
                'Source': f'llm_{self.llm.get_provider_name()}',
                'is_asset': True
            }
        else:
            std_id = f"MAT-{self.mat_counter:05d}"
            self.mat_counter += 1
            return {
                'Standardized_ID': std_id,
                'Standardized_Name': llm_result.get('standardized_name', ''),
                'Material_Type': llm_result.get('material_type', ''),
                'Material_Subtype': llm_result.get('material_subtype', ''),
                'Material_Code': old_code,
                'UOM': llm_result.get('uom', std_uom),
                'HSN_Code': llm_result.get('hsn_code', ''),
                'Status': 'Active',
                'Confidence_Score': llm_result.get('confidence', 85),
                'Original_Name': old_name,
                'Source': f'llm_{self.llm.get_provider_name()}',
                'is_asset': False
            }
    
    def _rule_based(self, name, mat_type, sub_type, uom, old_code, is_asset):
        """Rule-based standardization"""
        if is_asset:
            return self._rule_asset(name, mat_type, sub_type, old_code)
        return self._rule_material(name, mat_type, sub_type, uom, old_code)
    
    def _rule_material(self, name, mat_type, sub_type, uom, old_code):
        """Rule-based material standardization"""
        size = self._extract_size(name)
        color = self._extract_color(name)
        material = self._extract_material(name)
        hsn = self._get_hsn(mat_type, name)
        std_uom = self.config['uom_mapping'].get(uom.upper(), uom.upper())
        
        parts = []
        if mat_type:
            parts.append(mat_type.upper().replace(' ', '-'))
        if sub_type:
            parts.append(sub_type.upper().replace(' ', '-'))
        if size:
            parts.append(size)
        if material:
            parts.append(material)
        if color:
            parts.append(color)
        if not parts:
            parts.append(self._clean(name))
        
        std_name = re.sub(r'-+', '-', '-'.join(parts))
        
        std_id = f"MAT-{self.mat_counter:05d}"
        self.mat_counter += 1
        
        return {
            'Standardized_ID': std_id,
            'Standardized_Name': std_name,
            'Material_Type': mat_type.upper() if mat_type else 'UNKNOWN',
            'Material_Subtype': sub_type.upper() if sub_type else '',
            'Material_Code': old_code,
            'UOM': std_uom,
            'HSN_Code': hsn,
            'Status': 'Active',
            'Confidence_Score': 60,
            'Original_Name': name,
            'Source': 'rule_based',
            'is_asset': False
        }
    
    def _rule_asset(self, name, mat_type, sub_type, old_code):
        """Rule-based asset standardization"""
        plate = re.search(r'([A-Z]{3}\d{2,3}[A-Z]{2})', name)
        if plate:
            brands = ['TOYOTA', 'HONDA', 'NISSAN', 'MITSUBISHI', 'HYUNDAI', 'CHEVROLET', 'LEXUS', 'FORD', 'MERCEDES', 'BMW', 'KIA']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            models = ['CAMRY', 'ACCORD', 'CIVIC', 'CITY', 'SUNNY', 'LANCER', 'ELANTRA', 'CRUZE', 'AVENSIS', 'COROLLA', 'RX330', 'RX350']
            model = next((m for m in models if m in name), 'UNKNOWN')
            
            if 'SUV' in name:
                vtype = 'SUV'
            elif 'BUS' in name:
                vtype = 'BUS'
            elif 'TRUCK' in name:
                vtype = 'TRUCK'
            else:
                vtype = 'SEDAN'
            
            parts = ['VEHICLE', vtype, brand, model, plate.group(1)]
            return self._make_asset(name, '-'.join(parts), 'VEHICLE', vtype, '8703', old_code, 85)
        
        if 'GENERATOR' in name or 'GENSET' in name:
            kva = re.search(r'(\d+)\s*(KVA|KW)', name)
            brands = ['CUMMINS', 'PERKINS', 'CATERPILLAR', 'KOHLER', 'FG WILSON']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'GENERATOR-{brand}-{kva.group(1) if kva else "UNKNOWN"}KVA', 'GENERATOR', 'DG-SET', '8502', old_code, 75)
        
        if 'COMPRESSOR' in name:
            ton = re.search(r'(\d+)\s*TON', name)
            return self._make_asset(name, f'COMPRESSOR-SCROLL-{ton.group(1) if ton else "UNKNOWN"}TON', 'COMPRESSOR', 'SCROLL', '8414', old_code, 75)
        
        if 'CHILLER' in name:
            brands = ['TRANE', 'CARRIER', 'DAIKIN', 'YORK']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'CHILLER-{brand}-SCROLL', 'CHILLER', 'SCROLL', '8418', old_code, 70)
        
        if 'PUMP' in name:
            brands = ['MOVITEC', 'GRUNDFOS', 'DAB', 'KIRLOSKAR']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            kw = re.search(r'(\d+\.?\d*)\s*KW', name)
            return self._make_asset(name, f'PUMP-{brand}-{kw.group(1) if kw else "UNKNOWN"}KW', 'PUMP', 'WATER', '8413', old_code, 70)
        
        if 'AHU' in name or 'AIR HANDLING' in name:
            brands = ['TRANE', 'CARRIER', 'DAIKIN']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            cfm = re.search(r'(\d+)\s*CFM', name)
            return self._make_asset(name, f'AHU-{brand}-{cfm.group(1) if cfm else "UNKNOWN"}CFM', 'AHU', 'AIR-HANDLING', '8415', old_code, 70)
        
        if 'LIFT' in name or 'ELEVATOR' in name:
            brands = ['SCHINDLER', 'OTIS', 'KONE', 'MITSUBISHI', 'THYSSEN']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'LIFT-{brand}-ELEVATOR', 'LIFT', 'ELEVATOR', '8428', old_code, 75)
        
        if any(k in name for k in ['DESKTOP', 'LAPTOP', 'COMPUTER']):
            subtype = 'LAPTOP' if 'LAPTOP' in name else 'DESKTOP'
            return self._make_asset(name, f'COMPUTER-{subtype}', 'COMPUTER', subtype, '8471', old_code, 80)
        
        if 'AC' in name or 'AIR CONDITIONING' in name:
            brands = ['DAIKIN', 'TRANE', 'CARRIER', 'HITACHI', 'SAMSUNG', 'LG']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'AC-{brand}-SPLIT', 'AC', 'SPLIT', '8415', old_code, 70)
        
        clean = self._clean(name)
        hsn = self._get_hsn(mat_type, name)
        return self._make_asset(name, f'{mat_type.upper()}-{clean}' if mat_type else clean, mat_type.upper(), sub_type.upper(), hsn, old_code, 50)
    
    def _make_asset(self, orig, std_name, atype, subtype, hsn, code, conf):
        """Build asset result"""
        std_id = f"AST-{self.ast_counter:05d}"
        self.ast_counter += 1
        return {
            'Standardized_ID': std_id,
            'Standardized_Asset_Name': std_name,
            'Asset_Type': atype,
            'Asset_Subtype': subtype,
            'Old_Code': code,
            'UOM': 'UNIT',
            'HSN_Code': hsn,
            'Status': 'Active',
            'Confidence_Score': conf,
            'Original_Name': orig,
            'Source': 'rule_based',
            'is_asset': True
        }
    
    def _is_asset(self, name, mat_type):
        """Detect if item is an asset"""
        combined = f"{name} {mat_type}".upper()
        for kw in self.config['asset_detection']['keywords']:
            if kw.upper() in combined:
                return True
        if re.search(self.config['asset_detection']['plate_pattern'], name):
            return True
        return False
    
    def _clean(self, text):
        """Clean and normalize text"""
        text = re.sub(r'[^\w\s\-]', '', text.upper())
        text = re.sub(r'\s+', '-', text)
        return re.sub(r'-+', '-', text)
    
    def _extract_size(self, name):
        """Extract size from name"""
        m = re.search(r'(\d+)\s*[C]\s*[Xx]\s*(\d+\.?\d*)\s*(MM|SQMM)?', name)
        if m:
            return f"{m.group(1)}C-{m.group(2)}{m.group(3) or 'MM'}"
        m = re.search(r'(\d+\.?\d*)\s*(MM|CM|INCH|SQMM|METER)', name)
        if m:
            return f"{m.group(1)}{m.group(2)}"
        m = re.search(r'(\d+/\d+)\s*"?', name)
        if m:
            return f"{m.group(1)}INCH"
        m = re.search(r'(\d+)\s*(A|AMP|AMPS)', name)
        if m:
            return f"{m.group(1)}A"
        m = re.search(r'(\d+)\s*(W|WATT|WATTS)', name)
        if m:
            return f"{m.group(1)}W"
        m = re.search(r'(\d+)\s*(TON|TR)', name)
        if m:
            return f"{m.group(1)}TON"
        return ""
    
    def _extract_color(self, name):
        """Extract color from name"""
        colors = ['BLACK', 'WHITE', 'RED', 'BLUE', 'GREEN', 'YELLOW', 'BROWN', 'GREY', 'GRAY', 'ORANGE', 'PINK', 'PURPLE']
        return next((c for c in colors if c in name), "")
    
    def _extract_material(self, name):
        """Extract material from name"""
        mats = ['COPPER', 'ALUMINIUM', 'ALUMINUM', 'STEEL', 'IRON', 'BRASS', 'PVC', 'GI', 'SS', 'RUBBER', 'NYLON', 'STAINLESS']
        return next((m for m in mats if m in name), "")
    
    def _get_hsn(self, mat_type, name):
        """Get HSN code based on material type and name"""
        combined = f"{mat_type} {name}".upper().replace(' ', '_')
        for key, code in self.hsn_map.items():
            if key in combined:
                return code
        return self.hsn_map.get('DEFAULT', '8479')