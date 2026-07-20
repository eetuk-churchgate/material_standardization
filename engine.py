"""
DUAL-MODE ENGINE
Mode 1: Convert Format + HSN (Fast) - Format conversion + HSN assignment
Mode 2: AI Standardize (Smart) - AI-powered standardization from scratch
"""
import pandas as pd
import numpy as np
from pathlib import Path
import re
import yaml
import pickle
import os
from io import BytesIO
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
        self.uom_map = self.config.get('uom_mapping', {})
        self.llm_calls = 0
        self.fast_calls = 0
        self.progress_callback = None
        self.batch_size = 500
        self.master_file_path = "data/master_data.pkl"
        self.mode = "convert"
        
        self._auto_load_master()
        print(f"Engine ready | Mode: {self.mode} | LLM: {self.llm.get_provider_name()} | Master: {len(self.master_names)}")
    
    def set_mode(self, mode):
        """Set processing mode: 'standardize' or 'convert'"""
        self.mode = mode
        print(f"Mode set to: {mode}")
    
    def _auto_load_master(self):
        if Path(self.master_file_path).exists():
            try:
                self.load_master_data()
            except:
                pass
    
    def set_progress_callback(self, callback):
        self.progress_callback = callback
    
    def learn_from_master(self, file_path):
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
                found = True
                break
        
        if not found:
            for col in df.columns:
                if df[col].dtype == 'object':
                    new_names.extend(df[col].dropna().astype(str).str.upper().str.strip().tolist())
        
        before = len(self.master_names)
        self.master_names.extend(new_names)
        self.master_names = list(set([n for n in self.master_names if n and len(n) > 2]))
        added = len(self.master_names) - before
        
        self.save_master_data()
        print(f"Added {added} names. Total: {len(self.master_names)}")
        return added
    
    def save_master_data(self, filepath=None):
        if filepath is None:
            filepath = self.master_file_path
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        data = {
            'master_names': self.master_names,
            'master_df': self.master_df.to_dict() if self.master_df is not None else None
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    def load_master_data(self, filepath=None):
        if filepath is None:
            filepath = self.master_file_path
        if Path(filepath).exists():
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            self.master_names = data.get('master_names', [])
            df_dict = data.get('master_df')
            if df_dict:
                self.master_df = pd.DataFrame.from_dict(df_dict)
            return True
        return False
    
    def clear_master_data(self):
        self.master_names = []
        self.master_df = None
        if Path(self.master_file_path).exists():
            os.remove(self.master_file_path)
    
    def export_master_to_excel(self):
        if not self.master_names:
            return None
        df = pd.DataFrame({'Standardized_Name': self.master_names})
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return output
    
    # ================================================================
    # MAIN PROCESSING
    # ================================================================
    
    def process_file(self, file_path):
        if self.mode == "convert":
            return self._process_convert(file_path)
        else:
            return self._process_standardize(file_path)
    
    # ================================================================
    # MODE 1: CONVERT FORMAT + ASSIGN HSN (FAST)
    # ================================================================
    
    def _process_convert(self, file_path):
        print(f"Converting: {Path(file_path).name}")
        
        df = self._read_file(file_path)
        if df is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        total = len(df)
        print(f"Rows: {total}")
        
        self.mat_counter = 1
        self.ast_counter = 1
        results = []
        
        for idx, row in df.iterrows():
            result = self._convert_row(row)
            if result:
                results.append(result)
            
            if (idx + 1) % 1000 == 0:
                if self.progress_callback:
                    pct = int((idx + 1) / total * 100)
                    self.progress_callback(pct, f"Converting: {idx+1}/{total}")
        
        if self.progress_callback:
            self.progress_callback(100, "Complete!")
        
        output_df = pd.DataFrame(results)
        print(f"Converted: {len(results)} rows")
        
        return output_df, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    def _convert_row(self, row):
        std_name = self._field(row, [
            'Standardized_Name', 'Standardized Name',
            'Standardized_Material_Name', 'Standardized Material_Name',
            'Standardized Material Name', 'Material_Name',
            'Standardized_Asset_Name', 'Standardized Asset_Name'
        ])
        
        category = self._field(row, [
            'Category', 'Material_Type', 'Material Type',
            'Standardized Material_Type', 'Standardized_Material_Type',
            'MaterialType', 'Asset_Type', 'Asset Type'
        ])
        
        subcategory = self._field(row, [
            'Sub-Category', 'Sub_Category', 'Sub Category',
            'Material_Subtype', 'Material_Subtype',
            'Standardized Material_Subtype', 'Standardized_Material_Subtype',
            'MaterialSubType', 'Asset_Subtype', 'Asset Subtype'
        ])
        
        original_name = self._field(row, [
            'Original_Name', 'Original Name',
            'MaterialName', 'Material_Name', 'Material Name',
            'Name', 'Description'
        ])
        
        material_code = self._field(row, [
            'Material_Code', 'Material Code',
            'MaterialCode', 'Old_Code', 'Old Code',
            'Code', 'ID', 'Id'
        ])
        
        uom = self._field(row, [
            'UOM', 'Unit', 'UnitOfMeasure', 'Unit_Of_Measure'
        ])
        
        existing_hsn = self._field(row, [
            'HSN_Code', 'HSN Code', 'HSNCode', 'HSN'
        ])
        
        key_attrs = self._field(row, [
            'Key_Attributes', 'Key Attributes',
            'Specifications', 'Specification'
        ])
        
        if not std_name:
            std_name = str(original_name) if original_name else "UNKNOWN"
        
        # HSN Assignment
        if existing_hsn and str(existing_hsn).strip() and len(str(existing_hsn).strip()) >= 4:
            hsn = str(existing_hsn).strip()
        else:
            search_text = f"{category} {subcategory} {std_name} {key_attrs}"
            hsn = self._get_hsn(search_text)
        
        # UOM Standardization
        std_uom = self.uom_map.get(str(uom).upper().strip(), str(uom).upper().strip()) if uom else "UNIT"
        
        # ID Generation
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
        print(f"Standardizing: {Path(file_path).name}")
        
        df = self._read_file(file_path)
        if df is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        total = len(df)
        print(f"Rows: {total} | Master names: {len(self.master_names)}")
        
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
        
        print(f"Done | Materials: {len(self.materials)} | Assets: {len(self.assets)}")
        return mat_df, ast_df, pd.DataFrame(), pd.DataFrame()
    
    def _standardize_row(self, row):
        old_name = self._field(row, ['MaterialName', 'Material_Name', 'Name', 'Description'])
        mat_type = self._field(row, ['MaterialType', 'Material_Type', 'Type', 'Category'])
        sub_type = self._field(row, ['MaterialSubType', 'Material_Subtype', 'SubType'])
        uom = self._field(row, ['UOM', 'Unit', 'UnitOfMeasure'])
        old_code = self._field(row, ['MaterialCode', 'Material_Code', 'Code', 'ID', 'Id'])
        
        if not old_name:
            return None
        
        old_name = str(old_name).strip()
        mat_type = str(mat_type).strip() if mat_type and pd.notna(mat_type) else ""
        sub_type = str(sub_type).strip() if sub_type and pd.notna(sub_type) else ""
        uom = str(uom).strip() if uom and pd.notna(uom) else "NOS"
        old_code = str(old_code).strip() if old_code and pd.notna(old_code) else ""
        name_upper = old_name.upper()
        
        # LAYER 1: Exact match
        if name_upper in self.master_names:
            self.fast_calls += 1
            return self._build_result(name_upper, old_code, uom, 100, 'exact_match')
        
        # LAYER 2: Fuzzy match
        if self.master_names:
            best = process.extractOne(name_upper, self.master_names, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 85:
                self.fast_calls += 1
                return self._build_result(best[0], old_code, uom, best[1], 'fuzzy_match')
        
        # LAYER 3: Rule-based
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
    
    def _rule_based(self, name, mat_type, sub_type, uom, old_code, is_asset):
        if is_asset:
            return self._rule_asset(name, mat_type, sub_type, old_code)
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
        plate = re.search(r'([A-Z]{3}\d{2,3}[A-Z]{2})', name)
        if plate:
            brands = ['TOYOTA', 'HONDA', 'NISSAN', 'MITSUBISHI', 'HYUNDAI', 'CHEVROLET', 'LEXUS', 'FORD', 'MERCEDES', 'BMW', 'KIA']
            brand = next((b for b in brands if b in name), 'UNKNOWN')
            models = ['CAMRY', 'ACCORD', 'CIVIC', 'CITY', 'SUNNY', 'LANCER', 'ELANTRA', 'CRUZE', 'AVENSIS', 'COROLLA', 'RX330', 'RX350']
            model = next((m for m in models if m in name), 'UNKNOWN')
            vtype = 'SUV' if 'SUV' in name else ('BUS' if 'BUS' in name else ('TRUCK' if 'TRUCK' in name else 'SEDAN'))
            return self._make_asset(name, f"VEHICLE-{vtype}-{brand}-{model}-{plate.group(1)}", 'VEHICLE', vtype, '8703', old_code, 85)
        
        if 'GENERATOR' in name:
            kva = re.search(r'(\d+)\s*(KVA|KW)', name)
            brands = ['CUMMINS', 'PERKINS', 'CATERPILLAR', 'KOHLER']
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
        hsn = self._get_hsn(f"{mat_type} {name}")
        return self._make_asset(name, f'{mat_type.upper()}-{clean}' if mat_type else clean, mat_type.upper(), sub_type.upper(), hsn, old_code, 50)
    
    def _make_asset(self, orig, std_name, atype, subtype, hsn, code, conf):
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
    
    # ================================================================
    # SHARED UTILITIES
    # ================================================================
    
    def _read_file(self, path):
        try:
            if str(path).endswith('.csv'):
                return pd.read_csv(path)
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
        keywords = [
            'VEHICLE', 'GENERATOR', 'COMPRESSOR', 'CHILLER', 'ELEVATOR',
            'LIFT', 'TRANSFORMER', 'PUMP', 'MOTOR', 'PANEL', 'AHU',
            'AIR HANDLING', 'FIRE EXTINGUISHER', 'DESKTOP', 'LAPTOP',
            'COMPUTER', 'SERVER', 'PRINTER', 'AC', 'AIR CONDITIONING'
        ]
        for kw in keywords:
            if kw in combined:
                return True
        if re.search(r'[A-Z]{3}\d{2,3}[A-Z]{2}', name):
            return True
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
        colors = ['BLACK', 'WHITE', 'RED', 'BLUE', 'GREEN', 'YELLOW', 'BROWN', 'GREY', 'GRAY', 'ORANGE']
        return next((c for c in colors if c in name), "")
    
    def _extract_material(self, name):
        mats = ['COPPER', 'ALUMINIUM', 'STEEL', 'IRON', 'BRASS', 'PVC', 'GI', 'SS', 'RUBBER', 'NYLON']
        return next((m for m in mats if m in name), "")
    
    def _guess_type(self, name):
        name_upper = str(name).upper()
        type_map = {
            'CABLE': ['CABLE', 'WIRE'],
            'LUG': ['LUG', 'GLAND'],
            'CABLE-TIE': ['CABLE TIE'],
            'MCB': ['MCB', 'MCCB', 'BREAKER'],
            'SWITCH': ['SWITCH', 'CHANGEOVER'],
            'CHOKE': ['CHOKE', 'TRANSFORMER'],
            'BEARING': ['BEARING'],
            'FILTER': ['FILTER'],
            'BELT': ['BELT'],
            'PUMP': ['PUMP'],
            'VALVE': ['VALVE', 'NRV'],
            'PIPE': ['PIPE', 'TUBE'],
            'FITTING': ['TEE', 'ELBOW', 'SOCKET', 'FLANGE'],
            'CLAMP': ['CLAMP'],
            'PAINT': ['PAINT'],
            'CEMENT': ['CEMENT'],
            'TILE': ['TILE', 'MARBLE'],
            'LIGHTING': ['LED', 'LIGHT', 'BULB'],
            'COMPUTER': ['DESKTOP', 'LAPTOP', 'COMPUTER'],
            'VEHICLE': ['VEHICLE', 'CAR', 'SUV', 'BUS'],
        }
        for typ, keywords in type_map.items():
            for kw in keywords:
                if kw in name_upper:
                    return typ
        return 'UNKNOWN'
    
    def _get_hsn(self, search_text):
        """Get HSN code from search text"""
        search_upper = str(search_text).upper().replace(' ', '_')
        rules = [
            (['CABLE', 'WIRE', 'CONDUCTOR'], '8544'),
            (['MCB', 'MCCB', 'BREAKER', 'CHANGEOVER', 'CONTACTOR', 'SWITCH'], '8536'),
            (['LED', 'LIGHT', 'BULB', 'LAMP', 'FLOOD'], '9405'),
            (['CHOKE', 'TRANSFORMER'], '8504'),
            (['BEARING'], '8482'),
            (['FILTER'], '8421'),
            (['BELT'], '4010'),
            (['PUMP'], '8413'),
            (['COMPRESSOR'], '8414'),
            (['VALVE', 'NRV'], '8481'),
            (['PVC_PIPE', 'CPVC', 'UPVC'], '3917'),
            (['PIPE_GI', 'PIPE_MS', 'PIPE', 'TUBE'], '7306'),
            (['TEE', 'ELBOW', 'SOCKET', 'FLANGE', 'UNION', 'FITTING'], '7307'),
            (['CLAMP'], '7326'),
            (['CEMENT'], '2523'),
            (['PAINT', 'VARNISH'], '3209'),
            (['TILE', 'MARBLE', 'GRANITE'], '6907'),
            (['VEHICLE', 'CAR', 'SUV', 'BUS', 'TRUCK'], '8703'),
            (['GENERATOR', 'GENSET'], '8502'),
            (['COMPUTER', 'LAPTOP', 'DESKTOP'], '8471'),
            (['AC', 'AIR_CONDITIONING', 'CHILLER', 'AHU'], '8415'),
            (['LIFT', 'ELEVATOR'], '8428'),
            (['DRUG', 'MEDICINE', 'TABLET'], '3004'),
            (['EXTINGUISHER', 'SPRINKLER'], '8424'),
            (['MOTOR'], '8501'),
            (['PANEL'], '8537'),
            (['LUG', 'GLAND', 'CABLE_TIE', 'CONNECTOR'], '8536'),
            (['DIFFUSER', 'GRILL'], '7616'),
        ]
        for keywords, hsn in rules:
            if any(kw in search_upper for kw in keywords):
                return hsn
        return '8479'