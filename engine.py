"""
CORE AI ENGINE - Streamlit Cloud Compatible
No sentence-transformers dependency
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import re
import yaml
from rapidfuzz import fuzz, process

from llm_handler import LLMHandler

class MaterialAIEngine:
    """AI Engine - works with or without LLM keys"""
    
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
        
        print(f"Engine ready | LLM: {self.llm.get_provider_name()}")
    
    def learn_from_master(self, file_path):
        """Learn from standardized master Excel file"""
        print(f"Learning from: {file_path}")
        
        try:
            df = pd.read_excel(file_path)
        except:
            xl = pd.ExcelFile(file_path)
            dfs = [pd.read_excel(file_path, sheet_name=s) for s in xl.sheet_names]
            df = pd.concat(dfs, ignore_index=True)
        
        self.master_df = df
        
        for col in ['Standardized_Name', 'Standardized_Asset_Name', 'Standardized_Material_Name']:
            if col in df.columns:
                self.master_names.extend(df[col].dropna().str.upper().tolist())
        
        print(f"Learned {len(self.master_names)} names")
        return len(self.master_names)
    
    def process_file(self, file_path):
        """Main processing pipeline"""
        print(f"Processing: {Path(file_path).name}")
        print(f"LLM: {self.llm.get_provider_name()}")
        
        df = self._read_file(file_path)
        if df is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        print(f"Rows: {len(df)}")
        
        self.mat_counter = 1
        self.ast_counter = 1
        self.materials = []
        self.assets = []
        self.audit = []
        self.review = []
        
        for idx, row in df.iterrows():
            result = self._process_row(row)
            if result:
                if result.get('is_asset'):
                    self.assets.append(result)
                else:
                    self.materials.append(result)
        
        mat_df = pd.DataFrame(self.materials) if self.materials else pd.DataFrame()
        ast_df = pd.DataFrame(self.assets) if self.assets else pd.DataFrame()
        aud_df = pd.DataFrame(self.audit) if self.audit else pd.DataFrame()
        rev_df = pd.DataFrame(self.review) if self.review else pd.DataFrame()
        
        print(f"Done - Materials: {len(self.materials)}, Assets: {len(self.assets)}, Review: {len(self.review)}")
        
        return mat_df, ast_df, aud_df, rev_df
    
    def _read_file(self, path):
        try:
            if str(path).endswith('.csv'):
                return pd.read_csv(path)
            return pd.read_excel(path)
        except Exception as e:
            print(f"Error reading file: {e}")
        return None
    
    def _process_row(self, row):
        old_name = self._field(row, ['MaterialName', 'Material_Name', 'Name', 'Description'])
        mat_type = self._field(row, ['MaterialType', 'Material_Type', 'Type'])
        sub_type = self._field(row, ['MaterialSubType', 'Material_Subtype', 'SubType'])
        uom = self._field(row, ['UOM', 'Unit', 'UnitOfMeasure'])
        old_code = self._field(row, ['MaterialCode', 'Material_Code', 'Code'])
        
        if not old_name:
            return None
        
        old_name = str(old_name).strip()
        mat_type = str(mat_type).strip() if mat_type else ""
        sub_type = str(sub_type).strip() if sub_type else ""
        uom = str(uom).strip() if uom else "NOS"
        old_code = str(old_code).strip() if old_code else ""
        
        result = self._standardize(old_name, mat_type, sub_type, uom, old_code)
        
        self.audit.append({
            'Original': old_name,
            'Standardized': result.get('Standardized_Name', result.get('Standardized_Asset_Name', '')),
            'Confidence': result.get('Confidence_Score', 0),
            'Source': result.get('Source', 'unknown')
        })
        
        threshold = self.config['engine']['confidence_threshold']
        if result.get('Confidence_Score', 0) < threshold:
            self.review.append(result)
        
        return result
    
    def _field(self, row, names):
        for n in names:
            if n in row.index and pd.notna(row[n]) and str(row[n]).strip():
                return row[n]
        return ""
    
    def _standardize(self, name, mat_type, sub_type, uom, old_code):
        name_upper = name.upper()
        is_asset = self._is_asset(name_upper, mat_type)
        
        # Layer 1: Exact match
        result = self._exact_match(name_upper, is_asset, old_code, uom)
        if result:
            return result
        
        # Layer 2: Fuzzy match
        result = self._fuzzy_match(name_upper, is_asset, old_code, uom)
        if result and result['Confidence_Score'] >= 85:
            return result
        
        # Layer 3: LLM
        if self.llm.is_available():
            llm_result = self.llm.standardize(name, mat_type, sub_type, uom, is_asset)
            if llm_result:
                return self._format_llm_result(llm_result, name, old_code, uom, is_asset)
        
        # Layer 4: Rule-based
        return self._rule_based(name_upper, mat_type, sub_type, uom, old_code, is_asset)
    
    def _exact_match(self, name, is_asset, old_code, uom):
        if name not in self.master_names:
            return None
        idx = self.master_names.index(name)
        row = self.master_df.iloc[idx] if self.master_df is not None else None
        result = self._build_result(name, is_asset, old_code, uom, 100, 'exact_match')
        if row is not None:
            for col in ['Standardized_Name', 'Standardized_Asset_Name', 'HSN_Code', 'UOM']:
                if col in row.index and pd.notna(row[col]):
                    result[col] = row[col]
        return result
    
    def _fuzzy_match(self, name, is_asset, old_code, uom):
        if not self.master_names:
            return None
        threshold = self.config['engine']['fuzzy_threshold']
        best = process.extractOne(name, self.master_names, scorer=fuzz.token_sort_ratio)
        if best and best[1] >= threshold:
            idx = self.master_names.index(best[0])
            row = self.master_df.iloc[idx] if self.master_df is not None else None
            result = self._build_result(name, is_asset, old_code, uom, best[1], 'fuzzy_match')
            if row is not None:
                for col in ['Standardized_Name', 'Standardized_Asset_Name', 'HSN_Code', 'UOM']:
                    if col in row.index and pd.notna(row[col]):
                        result[col] = row[col]
            return result
        return None
    
    def _format_llm_result(self, llm_result, name, old_code, uom, is_asset):
        std_uom = self.config['uom_mapping'].get(uom.upper(), uom.upper())
        if is_asset:
            std_id = f"{self.config['output']['asset_id_prefix']}{self.ast_counter:05d}"
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
                'Original_Name': name,
                'Source': f'llm_{self.llm.get_provider_name()}',
                'is_asset': True
            }
        else:
            std_id = f"{self.config['output']['material_id_prefix']}{self.mat_counter:05d}"
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
                'Original_Name': name,
                'Source': f'llm_{self.llm.get_provider_name()}',
                'is_asset': False
            }
    
    def _rule_based(self, name, mat_type, sub_type, uom, old_code, is_asset):
        if is_asset:
            return self._rule_asset(name, mat_type, sub_type, old_code)
        else:
            return self._rule_material(name, mat_type, sub_type, uom, old_code)
    
    def _rule_material(self, name, mat_type, sub_type, uom, old_code):
        clean = re.sub(r'[^\w\s\-]', '', name).replace(' ', '-')
        clean = re.sub(r'-+', '-', clean)
        size = self._extract_size(name)
        color = self._extract_color(name)
        material = self._extract_material(name)
        hsn = self._get_hsn(mat_type, name)
        std_uom = self.config['uom_mapping'].get(uom.upper(), uom.upper())
        
        parts = []
        if mat_type: parts.append(mat_type.upper().replace(' ', '-'))
        if sub_type: parts.append(sub_type.upper().replace(' ', '-'))
        if size: parts.append(size)
        if material: parts.append(material)
        if color: parts.append(color)
        if not parts: parts.append(clean)
        
        std_name = re.sub(r'-+', '-', '-'.join(parts))
        
        std_id = f"{self.config['output']['material_id_prefix']}{self.mat_counter:05d}"
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
            'Confidence_Score': 55,
            'Original_Name': name,
            'Source': 'rule_based',
            'is_asset': False
        }
    
    def _rule_asset(self, name, mat_type, sub_type, old_code):
        plate = re.search(r'([A-Z]{3}\d{2,3}[A-Z]{2})', name)
        if plate:
            brands = ['TOYOTA','HONDA','NISSAN','MITSUBISHI','HYUNDAI','CHEVROLET','LEXUS','FORD','MERCEDES','BMW','KIA']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            models = ['CAMRY','ACCORD','CIVIC','CITY','SUNNY','LANCER','ELANTRA','CRUZE','AVENSIS','COROLLA','RX330','RX350']
            model = next((m for m in models if m in name), 'UNKNOWN')
            vtype = 'SUV' if 'SUV' in name else ('BUS' if 'BUS' in name else ('TRUCK' if 'TRUCK' in name else 'SEDAN'))
            parts = ['VEHICLE', vtype, brand, model, plate.group(1)]
            std_name = '-'.join(parts)
            return self._make_asset(name, std_name, 'VEHICLE', vtype, '8703', old_code, 85)
        
        if 'GENERATOR' in name:
            kva = re.search(r'(\d+)\s*(KVA|KW)', name)
            brands = ['CUMMINS','PERKINS','CATERPILLAR','KOHLER']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            std_name = f'GENERATOR-{brand}-{kva.group(1) if kva else "UNKNOWN"}KVA'
            return self._make_asset(name, std_name, 'GENERATOR', 'DG-SET', '8502', old_code, 75)
        
        if 'COMPRESSOR' in name:
            ton = re.search(r'(\d+)\s*TON', name)
            std_name = f'COMPRESSOR-SCROLL-{ton.group(1) if ton else "UNKNOWN"}TON'
            return self._make_asset(name, std_name, 'COMPRESSOR', 'SCROLL', '8414', old_code, 75)
        
        if 'CHILLER' in name:
            brands = ['TRANE','CARRIER','DAIKIN','YORK']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'CHILLER-{brand}-SCROLL', 'CHILLER', 'SCROLL', '8418', old_code, 70)
        
        if 'PUMP' in name:
            brands = ['MOVITEC','GRUNDFOS','DAB','KIRLOSKAR']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            kw = re.search(r'(\d+\.?\d*)\s*KW', name)
            return self._make_asset(name, f'PUMP-{brand}-{kw.group(1) if kw else "UNKNOWN"}KW', 'PUMP', 'WATER', '8413', old_code, 70)
        
        if 'AHU' in name or 'AIR HANDLING' in name:
            brands = ['TRANE','CARRIER','DAIKIN']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            cfm = re.search(r'(\d+)\s*CFM', name)
            return self._make_asset(name, f'AHU-{brand}-{cfm.group(1) if cfm else "UNKNOWN"}CFM', 'AHU', 'AIR-HANDLING', '8415', old_code, 70)
        
        if 'LIFT' in name or 'ELEVATOR' in name:
            brands = ['SCHINDLER','OTIS','KONE','MITSUBISHI','THYSSEN']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            return self._make_asset(name, f'LIFT-{brand}-ELEVATOR', 'LIFT', 'ELEVATOR', '8428', old_code, 75)
        
        if any(k in name for k in ['DESKTOP','LAPTOP','COMPUTER']):
            subtype = 'LAPTOP' if 'LAPTOP' in name else 'DESKTOP'
            return self._make_asset(name, f'COMPUTER-{subtype}', 'COMPUTER', subtype, '8471', old_code, 80)
        
        clean = re.sub(r'[^\w\s\-]', '', name).replace(' ', '-')
        clean = re.sub(r'-+', '-', clean)
        hsn = self._get_hsn(mat_type, name)
        return self._make_asset(name, f'{mat_type.upper()}-{clean}' if mat_type else clean, mat_type.upper(), sub_type.upper(), hsn, old_code, 50)
    
    def _make_asset(self, orig, std_name, atype, subtype, hsn, code, conf):
        std_id = f"{self.config['output']['asset_id_prefix']}{self.ast_counter:05d}"
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
    
    def _build_result(self, name, is_asset, old_code, uom, confidence, source):
        std_uom = self.config['uom_mapping'].get(uom.upper(), uom.upper())
        if is_asset:
            std_id = f"{self.config['output']['asset_id_prefix']}{self.ast_counter:05d}"
            self.ast_counter += 1
            return {
                'Standardized_ID': std_id,
                'Standardized_Asset_Name': name,
                'Asset_Type': '', 'Asset_Subtype': '', 'Old_Code': old_code,
                'UOM': 'UNIT', 'HSN_Code': '', 'Status': 'Active',
                'Confidence_Score': confidence, 'Original_Name': name,
                'Source': source, 'is_asset': True
            }
        else:
            std_id = f"{self.config['output']['material_id_prefix']}{self.mat_counter:05d}"
            self.mat_counter += 1
            return {
                'Standardized_ID': std_id,
                'Standardized_Name': name,
                'Material_Type': '', 'Material_Subtype': '', 'Material_Code': old_code,
                'UOM': std_uom, 'HSN_Code': '', 'Status': 'Active',
                'Confidence_Score': confidence, 'Original_Name': name,
                'Source': source, 'is_asset': False
            }
    
    def _is_asset(self, name, mat_type):
        combined = f"{name} {mat_type}".upper()
        for kw in self.config['asset_detection']['keywords']:
            if kw.upper() in combined:
                return True
        if re.search(self.config['asset_detection']['plate_pattern'], name):
            return True
        return False
    
    def _extract_size(self, name):
        m = re.search(r'(\d+)\s*[C]\s*[Xx]\s*(\d+\.?\d*)\s*(MM|SQMM)?', name)
        if m: return f"{m.group(1)}C-{m.group(2)}{m.group(3) or 'MM'}"
        m = re.search(r'(\d+\.?\d*)\s*(MM|CM|INCH|SQMM|METER)', name)
        if m: return f"{m.group(1)}{m.group(2)}"
        m = re.search(r'(\d+/\d+)\s*"?', name)
        if m: return f"{m.group(1)}INCH"
        return ""
    
    def _extract_color(self, name):
        colors = ['BLACK','WHITE','RED','BLUE','GREEN','YELLOW','BROWN','GREY','GRAY','ORANGE']
        return next((c for c in colors if c in name), "")
    
    def _extract_material(self, name):
        mats = ['COPPER','ALUMINIUM','STEEL','IRON','BRASS','PVC','GI','SS','RUBBER','NYLON']
        return next((m for m in mats if m in name), "")
    
    def _get_hsn(self, mat_type, name):
        combined = f"{mat_type} {name}".upper().replace(' ', '_')
        for key, code in self.hsn_map.items():
            if key in combined:
                return code
        return self.hsn_map.get('DEFAULT', '8479')