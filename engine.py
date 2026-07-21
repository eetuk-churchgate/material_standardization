"""
ENTERPRISE AI ENGINE - UpGrade
=========================================
Dual Mode + Quick Lookup + Duplicate Detection + Quality Scoring
+ Anomaly Detection + Smart Suggestions + Export Multi-Format
"""
import pandas as pd
import numpy as np
from pathlib import Path
import re
import yaml
import pickle
import os
import json
from io import BytesIO
from datetime import datetime
from rapidfuzz import fuzz, process
from collections import Counter

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
        self.duplicates_found = []
        self.hsn_map = self.config.get('hsn_codes', {})
        self.uom_map = self.config.get('uom_mapping', {})
        self.llm_calls = 0
        self.fast_calls = 0
        self.progress_callback = None
        self.batch_size = 500
        self.master_file_path = "data/master_data.pkl"
        self.mode = "convert"
        self.processing_history = []
        self.quality_score = 0
        
        self._auto_load_master()
        print(f"🚀 Enterprise Engine Ready | Mode: {self.mode} | LLM: {self.llm.get_provider_name()} | Master: {len(self.master_names)}")
    
    # ================================================================
    # CONFIGURATION
    # ================================================================
    
    def set_mode(self, mode):
        self.mode = mode
        print(f"Mode: {mode}")
    
    def _auto_load_master(self):
        if Path(self.master_file_path).exists():
            try:
                self.load_master_data()
            except:
                pass
    
    def set_progress_callback(self, callback):
        self.progress_callback = callback
    
    # ================================================================
    # MASTER DATA MANAGEMENT
    # ================================================================
    
    def learn_from_master(self, file_path):
        print(f"📚 Learning: {file_path}")
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
            'Standardized Material_Name', 'MaterialName', 'Material_Name', 'Standardized Name'
        ]
        
        new_names = []
        for col in name_columns:
            if col in df.columns:
                new_names = df[col].dropna().astype(str).str.upper().str.strip().tolist()
                break
        
        if not new_names:
            for col in df.columns:
                if df[col].dtype == 'object':
                    new_names.extend(df[col].dropna().astype(str).str.upper().str.strip().tolist())
        
        before = len(self.master_names)
        self.master_names.extend(new_names)
        self.master_names = list(set([n for n in self.master_names if n and len(n) > 2]))
        added = len(self.master_names) - before
        
        self.save_master_data()
        print(f"✅ Added {added} names. Total: {len(self.master_names)}")
        return added
    
    def save_master_data(self, filepath=None):
        if filepath is None: filepath = self.master_file_path
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump({'master_names': self.master_names, 'master_df': self.master_df.to_dict() if self.master_df is not None else None}, f)
    
    def load_master_data(self, filepath=None):
        if filepath is None: filepath = self.master_file_path
        if Path(filepath).exists():
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            self.master_names = data.get('master_names', [])
            df_dict = data.get('master_df')
            if df_dict: self.master_df = pd.DataFrame.from_dict(df_dict)
            return True
        return False
    
    def clear_master_data(self):
        self.master_names = []
        self.master_df = None
        if Path(self.master_file_path).exists(): os.remove(self.master_file_path)
    
    def export_master_to_excel(self):
        if not self.master_names: return None
        df = pd.DataFrame({'Standardized_Name': self.master_names})
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return output
    
    # ================================================================
    # MAIN PROCESSING ROUTER
    # ================================================================
    
    def process_file(self, file_path):
        if self.mode == "convert":
            result = self._process_convert(file_path)
        else:
            result = self._process_standardize(file_path)
        
        # Record history
        self.processing_history.append({
            'timestamp': datetime.now().isoformat(),
            'mode': self.mode,
            'file': str(file_path),
            'rows': len(result[0]) if result[0] is not None else 0
        })
        
        return result
    
    # ================================================================
    # QUICK SINGLE ITEM LOOKUP
    # ================================================================
    
    def lookup_single(self, name, mat_type="", sub_type="", uom="NOS"):
        """Instant single item standardization"""
        name_upper = str(name).strip().upper()
        mat_type = str(mat_type).strip() if mat_type else ""
        sub_type = str(sub_type).strip() if sub_type else ""
        uom = str(uom).strip() if uom else "NOS"
        
        # Master exact match
        if name_upper in self.master_names:
            return self._build_lookup_result(name_upper, mat_type, sub_type, uom, 100, 'exact_match')
        
        # Fuzzy match
        if self.master_names:
            best = process.extractOne(name_upper, self.master_names, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 80:
                return self._build_lookup_result(best[0], mat_type, sub_type, uom, best[1], 'fuzzy_match')
        
        # Rule-based
        is_asset = self._is_asset(name_upper, mat_type)
        
        if is_asset:
            asset_result = self._rule_asset(name_upper, mat_type, sub_type, "")
            if asset_result:
                return {
                    'Material_ID': asset_result.get('Standardized_ID', ''),
                    'Standardized Material_Type': asset_result.get('Asset_Type', ''),
                    'Standardized Material_Subtype': asset_result.get('Asset_Subtype', ''),
                    'Standardized Material_Name': asset_result.get('Standardized_Asset_Name', ''),
                    'Material_Code': '',
                    'UOM': 'UNIT',
                    'HSN_Code': asset_result.get('HSN_Code', ''),
                    'Status': 'Active',
                    'Confidence': asset_result.get('Confidence_Score', 70)
                }
        
        return self._build_lookup_result(name_upper, mat_type, sub_type, uom, 60, 'rule_based')
    
    def _build_lookup_result(self, name, mat_type, sub_type, uom, confidence, source):
        size = self._extract_size(name)
        color = self._extract_color(name)
        material = self._extract_material(name)
        hsn = self._get_hsn(f"{mat_type} {name}")
        std_uom = self.uom_map.get(uom.upper(), uom.upper())
        
        parts = []
        if mat_type: parts.append(mat_type.upper().replace(' ', '-'))
        if sub_type: parts.append(sub_type.upper().replace(' ', '-'))
        if size: parts.append(size)
        if material: parts.append(material)
        if color: parts.append(color)
        if not parts: parts.append(self._clean(name))
        
        std_name = re.sub(r'-+', '-', '-'.join(parts))
        
        return {
            'Material_ID': f"MAT-{self.mat_counter:05d}",
            'Standardized Material_Type': mat_type.upper() if mat_type else self._guess_type(name),
            'Standardized Material_Subtype': sub_type.upper() if sub_type else '',
            'Standardized Material_Name': std_name,
            'Material_Code': '',
            'UOM': std_uom,
            'HSN_Code': hsn,
            'Status': 'Active',
            'Confidence': confidence,
            'Source': source
        }
    
    # ================================================================
    # MODE 1: CONVERT FORMAT + HSN (FAST)
    # ================================================================
    
    def _process_convert(self, file_path):
        print(f"⚡ Converting: {Path(file_path).name}")
        
        df = self._read_file(file_path)
        if df is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        total = len(df)
        
        self.mat_counter = 1
        self.ast_counter = 1
        self.duplicates_found = []
        results = []
        seen_names = {}
        
        for idx, row in df.iterrows():
            result = self._convert_row(row)
            if result:
                # Duplicate detection
                std_name = result.get('Standardized Material_Name', '')
                if std_name in seen_names:
                    self.duplicates_found.append({
                        'name': std_name,
                        'first_row': seen_names[std_name],
                        'duplicate_row': idx + 2
                    })
                else:
                    seen_names[std_name] = idx + 2
                
                results.append(result)
            
            if (idx + 1) % 1000 == 0:
                if self.progress_callback:
                    pct = int((idx + 1) / total * 100)
                    self.progress_callback(pct, f"Converting: {idx+1}/{total}")
        
        if self.progress_callback:
            self.progress_callback(100, "Complete!")
        
        output_df = pd.DataFrame(results)
        
        # Calculate quality score
        hsn_filled = output_df['HSN_Code'].notna().sum() if 'HSN_Code' in output_df.columns else 0
        self.quality_score = round((hsn_filled / len(output_df)) * 100) if len(output_df) > 0 else 0
        
        print(f"✅ Converted: {len(results)} | Duplicates: {len(self.duplicates_found)} | Quality: {self.quality_score}%")
        
        return output_df, pd.DataFrame(), pd.DataFrame(self.duplicates_found) if self.duplicates_found else pd.DataFrame(), pd.DataFrame()
    
    def _convert_row(self, row):
        std_name = self._field(row, ['Standardized_Name', 'Standardized Name', 'Standardized_Material_Name', 'Standardized Material_Name', 'Material_Name', 'Standardized_Asset_Name'])
        category = self._field(row, ['Category', 'Material_Type', 'Standardized Material_Type', 'MaterialType', 'Asset_Type'])
        subcategory = self._field(row, ['Sub-Category', 'Sub_Category', 'Material_Subtype', 'Standardized Material_Subtype', 'MaterialSubType', 'Asset_Subtype'])
        original_name = self._field(row, ['Original_Name', 'MaterialName', 'Material_Name', 'Name', 'Description'])
        material_code = self._field(row, ['Material_Code', 'MaterialCode', 'Old_Code', 'Code', 'ID', 'Id'])
        uom = self._field(row, ['UOM', 'Unit', 'UnitOfMeasure'])
        existing_hsn = self._field(row, ['HSN_Code', 'HSNCode', 'HSN'])
        key_attrs = self._field(row, ['Key_Attributes', 'Specifications'])
        
        if not std_name: std_name = str(original_name) if original_name else "UNKNOWN"
        
        # HSN
        if existing_hsn and str(existing_hsn).strip() and len(str(existing_hsn).strip()) >= 4:
            hsn = str(existing_hsn).strip()
        else:
            hsn = self._get_hsn(f"{category} {subcategory} {std_name} {key_attrs}")
        
        # UOM
        std_uom = self.uom_map.get(str(uom).upper().strip(), str(uom).upper().strip()) if uom else "UNIT"
        
        # ID
        if self._is_asset(str(std_name), str(category)):
            std_id = f"AST-{self.ast_counter:05d}"
            self.ast_counter += 1
        else:
            std_id = f"MAT-{self.mat_counter:05d}"
            self.mat_counter += 1
        
        return {
            'Material_ID': std_id,
            'Standardized Material_Type': str(category).upper() if category else self._guess_type(std_name),
            'Standardized Material_Subtype': str(subcategory).upper() if subcategory else '',
            'Standardized Material_Name': str(std_name).upper(),
            'Material_Code': str(material_code) if material_code else '',
            'UOM': std_uom,
            'HSN_Code': hsn,
            'Status': 'Active'
        }
    
    # ================================================================
    # MODE 2: AI STANDARDIZE (SMART)
    # ================================================================
    
    def _process_standardize(self, file_path):
        print(f"🧠 Standardizing: {Path(file_path).name}")
        
        df = self._read_file(file_path)
        if df is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        total = len(df)
        
        self.mat_counter = 1
        self.ast_counter = 1
        self.materials = []
        self.assets = []
        self.llm_calls = 0
        self.fast_calls = 0
        
        num_batches = (total + self.batch_size - 1) // self.batch_size
        
        for batch_num in range(num_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, total)
            batch = df.iloc[start_idx:end_idx]
            
            for idx, row in batch.iterrows():
                result = self._standardize_row(row)
                if result:
                    if result.get('is_asset'):
                        self.assets.append(result)
                    else:
                        self.materials.append(result)
            
            pct = int((end_idx / total) * 100)
            if self.progress_callback:
                self.progress_callback(pct, f"Batch {batch_num+1}/{num_batches} | LLM: {self.llm_calls}")
        
        if self.progress_callback:
            self.progress_callback(100, "Complete!")
        
        mat_df = pd.DataFrame(self.materials) if self.materials else pd.DataFrame()
        ast_df = pd.DataFrame(self.assets) if self.assets else pd.DataFrame()
        
        self.quality_score = round((self.fast_calls / max(total, 1)) * 100)
        
        print(f"✅ Materials: {len(self.materials)} | Assets: {len(self.assets)} | Quality: {self.quality_score}%")
        return mat_df, ast_df, pd.DataFrame(), pd.DataFrame()
    
    def _standardize_row(self, row):
        old_name = self._field(row, ['MaterialName', 'Material_Name', 'Name', 'Description'])
        mat_type = self._field(row, ['MaterialType', 'Material_Type', 'Type', 'Category'])
        sub_type = self._field(row, ['MaterialSubType', 'Material_Subtype', 'SubType'])
        uom = self._field(row, ['UOM', 'Unit', 'UnitOfMeasure'])
        old_code = self._field(row, ['MaterialCode', 'Material_Code', 'Code', 'ID', 'Id'])
        
        if not old_name: return None
        
        old_name = str(old_name).strip()
        mat_type = str(mat_type).strip() if mat_type and pd.notna(mat_type) else ""
        sub_type = str(sub_type).strip() if sub_type and pd.notna(sub_type) else ""
        uom = str(uom).strip() if uom and pd.notna(uom) else "NOS"
        old_code = str(old_code).strip() if old_code and pd.notna(old_code) else ""
        name_upper = old_name.upper()
        
        if name_upper in self.master_names:
            self.fast_calls += 1
            return self._build_result(name_upper, old_code, uom, 100, 'exact_match')
        
        if self.master_names:
            best = process.extractOne(name_upper, self.master_names, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 85:
                self.fast_calls += 1
                return self._build_result(best[0], old_code, uom, best[1], 'fuzzy_match')
        
        is_asset = self._is_asset(name_upper, mat_type)
        result = self._rule_based(name_upper, mat_type, sub_type, uom, old_code, is_asset)
        self.fast_calls += 1
        return result
    
    def _build_result(self, std_name, old_code, uom, confidence, source):
        std_uom = self.uom_map.get(uom.upper(), uom.upper())
        hsn = self._get_hsn(std_name)
        std_id = f"MAT-{self.mat_counter:05d}"
        self.mat_counter += 1
        
        return {
            'Standardized_ID': std_id, 'Standardized_Name': std_name,
            'Material_Type': '', 'Material_Subtype': '',
            'Material_Code': old_code, 'UOM': std_uom,
            'HSN_Code': hsn, 'Status': 'Active',
            'Confidence_Score': confidence, 'Original_Name': std_name,
            'Source': source, 'is_asset': False
        }
    
    def _rule_based(self, name, mat_type, sub_type, uom, old_code, is_asset):
        if is_asset: return self._rule_asset(name, mat_type, sub_type, old_code)
        return self._rule_material(name, mat_type, sub_type, uom, old_code)
    
    def _rule_material(self, name, mat_type, sub_type, uom, old_code):
        size = self._extract_size(name)
        color = self._extract_color(name)
        material = self._extract_material(name)
        hsn = self._get_hsn(f"{mat_type} {name}")
        std_uom = self.uom_map.get(uom.upper(), uom.upper())
        
        parts = []
        if mat_type: parts.append(mat_type.upper().replace(' ', '-'))
        if sub_type: parts.append(sub_type.upper().replace(' ', '-'))
        if size: parts.append(size)
        if material: parts.append(material)
        if color: parts.append(color)
        if not parts: parts.append(self._clean(name))
        
        std_name = re.sub(r'-+', '-', '-'.join(parts))
        std_id = f"MAT-{self.mat_counter:05d}"
        self.mat_counter += 1
        
        return {
            'Standardized_ID': std_id, 'Standardized_Name': std_name,
            'Material_Type': mat_type.upper() if mat_type else 'UNKNOWN',
            'Material_Subtype': sub_type.upper() if sub_type else '',
            'Material_Code': old_code, 'UOM': std_uom,
            'HSN_Code': hsn, 'Status': 'Active',
            'Confidence_Score': 60, 'Original_Name': name,
            'Source': 'rule_based', 'is_asset': False
        }
    
    def _rule_asset(self, name, mat_type, sub_type, old_code):
        plate = re.search(r'([A-Z]{3}\d{2,3}[A-Z]{2})', name)
        if plate:
            brands = ['TOYOTA','HONDA','NISSAN','MITSUBISHI','HYUNDAI','CHEVROLET','LEXUS','FORD','MERCEDES','BMW','KIA']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            models = ['CAMRY','ACCORD','CIVIC','CITY','SUNNY','LANCER','ELANTRA','CRUZE','AVENSIS','COROLLA','RX330','RX350']
            model = next((m for m in models if m in name), 'UNKNOWN')
            vtype = 'SUV' if 'SUV' in name else ('BUS' if 'BUS' in name else ('TRUCK' if 'TRUCK' in name else 'SEDAN'))
            return self._make_asset(name, f"VEHICLE-{vtype}-{brand}-{model}-{plate.group(1)}", 'VEHICLE', vtype, '8703', old_code, 85)
        
        if 'GENERATOR' in name:
            kva = re.search(r'(\d+)\s*(KVA|KW)', name)
            brands = ['CUMMINS','PERKINS','CATERPILLAR','KOHLER']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'GENERATOR-{brand}-{kva.group(1) if kva else "UNKNOWN"}KVA', 'GENERATOR', 'DG-SET', '8502', old_code, 75)
        
        clean = self._clean(name)
        hsn = self._get_hsn(f"{mat_type} {name}")
        return self._make_asset(name, f'{mat_type.upper()}-{clean}' if mat_type else clean, mat_type.upper(), sub_type.upper(), hsn, old_code, 50)
    
    def _make_asset(self, orig, std_name, atype, subtype, hsn, code, conf):
        std_id = f"AST-{self.ast_counter:05d}"
        self.ast_counter += 1
        return {
            'Standardized_ID': std_id, 'Standardized_Asset_Name': std_name,
            'Asset_Type': atype, 'Asset_Subtype': subtype,
            'Old_Code': code, 'UOM': 'UNIT', 'HSN_Code': hsn,
            'Status': 'Active', 'Confidence_Score': conf,
            'Original_Name': orig, 'Source': 'rule_based', 'is_asset': True
        }
    
    # ================================================================
    # EXPORT FUNCTIONS
    # ================================================================
    
    def export_to_json(self, df):
        """Export dataframe to JSON"""
        if df is None or len(df) == 0: return "[]"
        return df.to_json(orient='records', indent=2)
    
    def export_to_sql(self, df, table_name="materials"):
        """Generate SQL INSERT statements"""
        if df is None or len(df) == 0: return ""
        sql = f"-- INSERT INTO {table_name}\n"
        for _, row in df.iterrows():
            values = []
            for val in row:
                if pd.isna(val):
                    values.append('NULL')
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    values.append(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'")
            sql += f"INSERT INTO {table_name} ({', '.join(df.columns)}) VALUES ({', '.join(values)});\n"
        return sql
    
    def get_quality_report(self):
        """Generate data quality report"""
        return {
            'quality_score': self.quality_score,
            'duplicates_found': len(self.duplicates_found),
            'hsn_coverage': self.quality_score,
            'master_names_loaded': len(self.master_names),
            'processing_history': self.processing_history[-5:] if self.processing_history else [],
            'llm_available': self.llm.is_available(),
            'llm_provider': self.llm.get_provider_name(),
            'mode': self.mode
        }
    
    # ================================================================
    # SHARED UTILITIES
    # ================================================================
    
    def _read_file(self, path):
        try:
            if str(path).endswith('.csv'): return pd.read_csv(path)
            return pd.read_excel(path)
        except Exception as e:
            print(f"Error: {e}")
        return None
    
    def _field(self, row, names):
        for n in names:
            if n in row.index and pd.notna(row[n]) and str(row[n]).strip():
                return row[n]
        return ""
    
    def _is_asset(self, name, category):
        combined = f"{name} {category}".upper()
        keywords = ['VEHICLE','GENERATOR','COMPRESSOR','CHILLER','ELEVATOR','LIFT','TRANSFORMER','PUMP','MOTOR','PANEL','AHU','AIR HANDLING','FIRE EXTINGUISHER','DESKTOP','LAPTOP','COMPUTER','SERVER','PRINTER','AC','AIR CONDITIONING']
        for kw in keywords:
            if kw in combined: return True
        if re.search(r'[A-Z]{3}\d{2,3}[A-Z]{2}', name): return True
        return False
    
    def _clean(self, text):
        text = re.sub(r'[^\w\s\-]', '', text.upper())
        text = re.sub(r'\s+', '-', text)
        return re.sub(r'-+', '-', text)
    
    def _extract_size(self, name):
        m = re.search(r'(\d+)\s*[C]\s*[Xx]\s*(\d+\.?\d*)\s*(MM|SQMM)?', name)
        if m: return f"{m.group(1)}C-{m.group(2)}{m.group(3) or 'MM'}"
        m = re.search(r'(\d+\.?\d*)\s*(MM|CM|INCH|SQMM|METER)', name)
        if m: return f"{m.group(1)}{m.group(2)}"
        m = re.search(r'(\d+/\d+)\s*"?', name)
        if m: return f"{m.group(1)}INCH"
        m = re.search(r'(\d+)\s*(A|AMP|AMPS)', name)
        if m: return f"{m.group(1)}A"
        return ""
    
    def _extract_color(self, name):
        colors = ['BLACK','WHITE','RED','BLUE','GREEN','YELLOW','BROWN','GREY','GRAY','ORANGE']
        return next((c for c in colors if c in name), "")
    
    def _extract_material(self, name):
        mats = ['COPPER','ALUMINIUM','STEEL','IRON','BRASS','PVC','GI','SS','RUBBER','NYLON']
        return next((m for m in mats if m in name), "")
    
    def _guess_type(self, name):
        name_upper = str(name).upper()
        type_map = {
            'CABLE': ['CABLE','WIRE'], 'LUG': ['LUG','GLAND'],
            'CABLE-TIE': ['CABLE TIE'], 'MCB': ['MCB','MCCB','BREAKER'],
            'SWITCH': ['SWITCH','CHANGEOVER'], 'CHOKE': ['CHOKE','TRANSFORMER'],
            'BEARING': ['BEARING'], 'FILTER': ['FILTER'], 'BELT': ['BELT'],
            'PUMP': ['PUMP'], 'VALVE': ['VALVE','NRV'],
            'PIPE': ['PIPE','TUBE'], 'FITTING': ['TEE','ELBOW','SOCKET','FLANGE'],
            'CLAMP': ['CLAMP'], 'PAINT': ['PAINT'], 'CEMENT': ['CEMENT'],
            'TILE': ['TILE','MARBLE'], 'LIGHTING': ['LED','LIGHT','BULB'],
            'COMPUTER': ['DESKTOP','LAPTOP','COMPUTER'],
            'VEHICLE': ['VEHICLE','CAR','SUV','BUS'],
        }
        for typ, keywords in type_map.items():
            for kw in keywords:
                if kw in name_upper: return typ
        return 'UNKNOWN'
    
    def _get_hsn(self, search_text):
        search_upper = str(search_text).upper().replace(' ', '_')
        rules = [
            (['CABLE','WIRE','CONDUCTOR'], '8544'),
            (['MCB','MCCB','BREAKER','CHANGEOVER','CONTACTOR','SWITCH'], '8536'),
            (['LED','LIGHT','BULB','LAMP','FLOOD'], '9405'),
            (['CHOKE','TRANSFORMER'], '8504'),
            (['BEARING'], '8482'), (['FILTER'], '8421'), (['BELT'], '4010'),
            (['PUMP'], '8413'), (['COMPRESSOR'], '8414'), (['VALVE','NRV'], '8481'),
            (['PVC_PIPE','CPVC','UPVC'], '3917'),
            (['PIPE_GI','PIPE_MS','PIPE','TUBE'], '7306'),
            (['TEE','ELBOW','SOCKET','FLANGE','UNION','FITTING'], '7307'),
            (['CLAMP'], '7326'), (['CEMENT'], '2523'), (['PAINT','VARNISH'], '3209'),
            (['TILE','MARBLE','GRANITE'], '6907'),
            (['VEHICLE','CAR','SUV','BUS','TRUCK'], '8703'),
            (['GENERATOR','GENSET'], '8502'),
            (['COMPUTER','LAPTOP','DESKTOP'], '8471'),
            (['AC','AIR_CONDITIONING','CHILLER','AHU'], '8415'),
            (['LIFT','ELEVATOR'], '8428'),
            (['DRUG','MEDICINE','TABLET'], '3004'),
            (['EXTINGUISHER','SPRINKLER'], '8424'),
            (['MOTOR'], '8501'), (['PANEL'], '8537'),
            (['LUG','GLAND','CABLE_TIE','CONNECTOR'], '8536'),
            (['DIFFUSER','GRILL'], '7616'),
        ]
        for keywords, hsn in rules:
            if any(kw in search_upper for kw in keywords): return hsn
        return '8479'
