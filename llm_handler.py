"""
LLM HANDLER
Connects to Groq (openai/gpt-oss-20b) or OpenAI.
Forces JSON output. Handles rate limits and parsing safely.
"""
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
        # Try Groq first (free, fast)
        if self.llm_config.get('groq', {}).get('enabled', False):
            api_key = os.getenv(self.llm_config['groq']['api_key_env'])
            if api_key:
                try:
                    from groq import Groq
                    self.clients['groq'] = Groq(api_key=api_key)
                    self.available_provider = 'groq'
                    print("✅ Groq LLM initialized")
                    return
                except ImportError:
                    print("❌ Groq library not installed")
                except Exception as e:
                    print(f"❌ Groq init error: {e}")
        
        # Try OpenAI fallback
        if self.llm_config.get('openai', {}).get('enabled', False):
            api_key = os.getenv(self.llm_config['openai']['api_key_env'])
            if api_key:
                try:
                    from openai import OpenAI
                    self.clients['openai'] = OpenAI(api_key=api_key)
                    self.available_provider = 'openai'
                    print("✅ OpenAI LLM initialized")
                    return
                except ImportError:
                    print("❌ OpenAI library not installed")
                except Exception as e:
                    print(f"❌ OpenAI init error: {e}")
        
        print("⚠️ No LLM keys found. Engine will use rule-based fallback.")
    
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
            print(f"❌ LLM API error: {e}")
            return None
    
    def _build_prompt(self, name, mat_type, sub_type, uom, is_asset):
        if is_asset:
            return f"""You are an ERP Asset Master Data Expert. Standardize this asset name.
RULES:
- Use ALL CAPS with hyphens (-).
- Format: CATEGORY-TYPE-BRAND-MODEL-ID
- Vehicles: VEHICLE-SEDAN-TOYOTA-CAMRY-BDG934BQ
- Generators: GENERATOR-CUMMINS-400KVA
- Pumps: PUMP-GRUNDFOS-CRE64-3KW
- AC: AC-DAIKIN-SPLIT
- Computers: COMPUTER-LAPTOP

Asset: {name}
Type: {mat_type}
Subtype: {sub_type}

Return ONLY a valid JSON object with EXACTLY these keys:
{{"standardized_name": "STRING", "asset_type": "STRING", "asset_subtype": "STRING", "hsn_code": "STRING", "confidence": 95}}"""
        else:
            return f"""You are an ERP Material Master Data Expert. Standardize this material name per ISO 8000.
RULES:
- Use ALL CAPS with hyphens (-).
- Format: CATEGORY-SUBCATEGORY-SIZE-SPEC
- Cables: CABLE-ARM-4C-16MM or CABLE-FLEXIBLE-3C-2.5SQMM
- Cable Lugs: LUG-CU-5.5SQMM-RING
- Breakers: MCB-63A-3POLE
- Bearings: BEARING-BALL-6206
- Pipes: PIPE-PVC-50MM

Material: {name}
Type: {mat_type}
Subtype: {sub_type}
UOM: {uom}

Return ONLY a valid JSON object with EXACTLY these keys:
{{"standardized_name": "STRING", "material_type": "STRING", "material_subtype": "STRING", "hsn_code": "STRING", "uom": "STRING", "confidence": 95}}"""
    
    def _call_groq(self, prompt):
        config = self.llm_config['groq']
        response = self.clients['groq'].chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "You are a strict JSON API. Return ONLY valid JSON. Do not include markdown formatting, explanations, or conversational text."},
                {"role": "user", "content": prompt}
            ],
            temperature=config.get('temperature', 0.1),
            max_tokens=config.get('max_tokens', 1000)
        )
        content = response.choices[0].message.content
        return self._parse_json(content)
    
    def _call_openai(self, prompt):
        config = self.llm_config['openai']
        response = self.clients['openai'].chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "You are a strict JSON API. Return ONLY valid JSON. Do not include markdown formatting, explanations, or conversational text."},
                {"role": "user", "content": prompt}
            ],
            temperature=config.get('temperature', 0.1),
            max_tokens=config.get('max_tokens', 500)
        )
        content = response.choices[0].message.content
        return self._parse_json(content)
    
    def _parse_json(self, text):
        # 1. Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # 2. Try extracting from markdown block
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # 3. Try extracting any JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        print(f"⚠️ Failed to parse JSON. Raw response: {text[:100]}...")
        return None