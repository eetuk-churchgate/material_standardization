"""LLM Handler - Groq / OpenAI / Fallback"""
import os
import json
import re
import yaml

class LLMHandler:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.llm_config = self.config.get('llm', {})
        self.clients = {}
        self.available_provider = None
        self._init_providers()
    
    def _init_providers(self):
        # Try Groq first (free)
        if self.llm_config.get('groq', {}).get('enabled', False):
            api_key = os.getenv(self.llm_config['groq']['api_key_env'])
            if api_key:
                try:
                    from groq import Groq
                    self.clients['groq'] = Groq(api_key=api_key)
                    self.available_provider = 'groq'
                    print("Groq ready")
                    return
                except ImportError:
                    print("Groq not installed")
                except Exception as e:
                    print(f"Groq error: {e}")
        
        # Try OpenAI
        if self.llm_config.get('openai', {}).get('enabled', False):
            api_key = os.getenv(self.llm_config['openai']['api_key_env'])
            if api_key:
                try:
                    from openai import OpenAI
                    self.clients['openai'] = OpenAI(api_key=api_key)
                    self.available_provider = 'openai'
                    print("OpenAI ready")
                    return
                except ImportError:
                    print("OpenAI not installed")
                except Exception as e:
                    print(f"OpenAI error: {e}")
        
        print("No LLM keys - rule-based mode")
    
    def is_available(self):
        return self.available_provider is not None
    
    def get_provider_name(self):
        return self.available_provider or "rule_based"
    
    def standardize(self, name, mat_type, sub_type, uom, is_asset=False):
        if not self.is_available():
            return None
        
        prompt = self._build_prompt(name, mat_type, sub_type, uom, is_asset)
        
        try:
            if self.available_provider == 'groq':
                return self._call_groq(prompt)
            elif self.available_provider == 'openai':
                return self._call_openai(prompt)
        except Exception as e:
            print(f"LLM error: {e}")
        
        return None
    
    def _build_prompt(self, name, mat_type, sub_type, uom, is_asset):
        if is_asset:
            return f"""Standardize this asset name. Use ALL CAPS with hyphens. Format: CATEGORY-TYPE-BRAND-MODEL-ID.
For vehicles: VEHICLE-SEDAN/SUV-BRAND-MODEL-PLATE
For generators: GENERATOR-BRAND-KVA
For compressors: COMPRESSOR-SCROLL-TON
For pumps: PUMP-BRAND-MODEL-KW
For chillers: CHILLER-BRAND-TYPE
For AHU: AHU-BRAND-MODEL-CFM
For lifts: LIFT-BRAND-ELEVATOR
For computers: COMPUTER-DESKTOP/LAPTOP
For AC: AC-BRAND-TYPE

Asset: {name}
Type: {mat_type}
Subtype: {sub_type}

Return ONLY JSON: {{"standardized_name": "...", "asset_type": "...", "asset_subtype": "...", "hsn_code": "...", "confidence": 90}}"""
        else:
            return f"""Standardize this material name per ISO 8000. Use ALL CAPS with hyphens.
Format: CATEGORY-SUBCATEGORY-SIZE-SPEC
Cables: CABLE-ARM-coresC-sizeMM or CABLE-FLEXIBLE-coresC-sizeSQMM
Lugs: LUG-CU-sizeSQMM-RING/PIN
Breakers: MCB-ampsA-polesPOLE or MCCB-ampsA-polesPOLE
Bearings: BEARING-TYPE-SIZE
Filters: FILTER-TYPE-CODE
Valves: VALVE-TYPE-SIZE
Pipes: PIPE-MATERIAL-SIZE
Extract size, color, material, amps, poles, cores from name.

Material: {name}
Type: {mat_type}
Subtype: {sub_type}
UOM: {uom}

Return ONLY JSON: {{"standardized_name": "...", "material_type": "...", "material_subtype": "...", "hsn_code": "...", "uom": "...", "confidence": 90}}"""
    
    def _call_groq(self, prompt):
        config = self.llm_config['groq']
        response = self.clients['groq'].chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=config['temperature'],
            max_tokens=config['max_tokens']
        )
        return self._parse_json(response.choices[0].message.content)
    
    def _call_openai(self, prompt):
        config = self.llm_config['openai']
        response = self.clients['openai'].chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=config['temperature'],
            max_tokens=config['max_tokens']
        )
        return self._parse_json(response.choices[0].message.content)
    
    def _parse_json(self, text):
        try:
            return json.loads(text)
        except:
            pass
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return None
