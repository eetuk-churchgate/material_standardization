"""
LLM HANDLER - Multi-Provider with No-Key Fallback
Priority: Groq → OpenAI → Rule-Based Fallback
All providers are optional - engine works without any API keys
"""
import os
import json
import re
import yaml

class LLMHandler:
    """Handles LLM calls with automatic provider fallback"""
    
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.llm_config = self.config.get('llm', {})
        self.clients = {}
        self.available_provider = None
        
        # Try initialize providers in priority order
        self._init_providers()
    
    def _init_providers(self):
        """Initialize LLM providers in priority order"""
        # Priority 1: Groq (free, fast)
        if self.llm_config.get('groq', {}).get('enabled', False):
            api_key = os.getenv(self.llm_config['groq']['api_key_env'])
            if api_key:
                try:
                    from groq import Groq
                    self.clients['groq'] = Groq(api_key=api_key)
                    self.available_provider = 'groq'
                    print("✅ Groq LLM ready (free tier)")
                    return
                except ImportError:
                    print("⚠️ Groq library not installed")
                except Exception as e:
                    print(f"⚠️ Groq init error: {e}")
        
        # Priority 2: OpenAI
        if self.llm_config.get('openai', {}).get('enabled', False):
            api_key = os.getenv(self.llm_config['openai']['api_key_env'])
            if api_key:
                try:
                    from openai import OpenAI
                    self.clients['openai'] = OpenAI(api_key=api_key)
                    self.available_provider = 'openai'
                    print("✅ OpenAI LLM ready")
                    return
                except ImportError:
                    print("⚠️ OpenAI library not installed")
                except Exception as e:
                    print(f"⚠️ OpenAI init error: {e}")
        
        # No provider available - will use rule-based fallback
        print("ℹ️ No LLM keys found - using rule-based standardization")
        print("ℹ️ Set GROQ_API_KEY or OPENAI_API_KEY for AI-powered mode")
    
    def is_available(self):
        """Check if any LLM is available"""
        return self.available_provider is not None
    
    def get_provider_name(self):
        """Get current provider name"""
        return self.available_provider or "rule_based"
    
    def standardize(self, name, mat_type, sub_type, uom, is_asset=False):
        """Standardize using best available provider"""
        if not self.is_available():
            return None
        
        prompt = self._build_prompt(name, mat_type, sub_type, uom, is_asset)
        
        try:
            if self.available_provider == 'groq':
                return self._call_groq(prompt)
            elif self.available_provider == 'openai':
                return self._call_openai(prompt)
        except Exception as e:
            print(f"⚠️ {self.available_provider} error: {e}, falling back")
            # Try next provider
            if self.available_provider == 'groq' and 'openai' in self.clients:
                try:
                    self.available_provider = 'openai'
                    return self._call_openai(prompt)
                except:
                    pass
        
        return None
    
    def _build_prompt(self, name, mat_type, sub_type, uom, is_asset):
        """Build standardization prompt"""
        if is_asset:
            return f"""You are an asset standardization expert. Convert this asset name to international standard format.

RULES:
- Use ALL CAPS with hyphens as separators
- Format: CATEGORY-TYPE-BRAND-MODEL-IDENTIFIER
- For vehicles: VEHICLE-SEDAN/SUV/BUS-{BRAND}-{MODEL}-{PLATE}
- For generators: GENERATOR-{BRAND}-{KVA}KVA
- For compressors: COMPRESSOR-SCROLL-{TON}TON
- For chillers: CHILLER-{BRAND}-{TYPE}
- For pumps: PUMP-{BRAND}-{MODEL}-{KW}KW
- For AHU: AHU-{BRAND}-{MODEL}-{CFM}CFM
- For lifts: LIFT-{BRAND}-ELEVATOR
- For computers: COMPUTER-{DESKTOP/LAPTOP}
- For AC: AC-{BRAND}-{TYPE}
- Extract brand, model, size, plate number from the name
- Use UNIT for asset UOM

ASSET TO STANDARDIZE:
Name: {name}
Type: {mat_type}
Subtype: {sub_type}

Return ONLY valid JSON:
{{"standardized_name": "...", "asset_type": "...", "asset_subtype": "...", "hsn_code": "...", "confidence": 90, "reasoning": "..."}}"""
        else:
            return f"""You are a material standardization expert. Convert this material name to international standard format per ISO 8000 and ECLASS.

RULES:
- Use ALL CAPS with hyphens
- Format: CATEGORY-SUBCATEGORY-SIZE-SPEC-UOM
- Cables: CABLE-ARM-{CORES}C-{SIZE}MM or CABLE-FLEXIBLE-{CORES}C-{SIZE}SQMM or CABLE-SINGLE-{SIZE}MM-{COLOR}
- Cable lugs: LUG-CU-{SIZE}SQMM-RING or LUG-CU-{SIZE}SQMM-PIN
- Cable ties: CABLE-TIE-{MATERIAL}-{SIZE}MM
- Circuit breakers: MCB-{AMPS}A-{POLES}POLE or MCCB-{AMPS}A-{POLES}POLE
- Chokes: CHOKE-{WATTS}W
- Bearings: BEARING-{TYPE}-{SIZE}
- Filters: FILTER-{TYPE}-{CODE}
- Valves: VALVE-{TYPE}-{SIZE}MM
- Pipes: PIPE-{MATERIAL}-{SIZE}MM or PIPE-{MATERIAL}-{SIZE}INCH
- Fittings: {TYPE}-{MATERIAL}-{SIZE}
- Ceiling diffusers: DIFFUSER-CEILING-{SIZE}MM
- Connectors: CONNECTOR-{TYPE}-{SIZE}
- Changeover switches: CHANGEOVER-{AMPS}A
- Drugs: DRUG-{NAME}
- Extract size (mm, inch, sqmm), color, material, amps, poles, cores, etc.
- Standardize measurements: mm, sqmm, inch
- Remove brand names from standardized name

MATERIAL TO STANDARDIZE:
Name: {name}
Type: {mat_type}
Subtype: {sub_type}
UOM: {uom}

Return ONLY valid JSON:
{{"standardized_name": "...", "material_type": "...", "material_subtype": "...", "hsn_code": "...", "uom": "...", "confidence": 90, "reasoning": "..."}}"""
    
    def _call_groq(self, prompt):
        """Call Groq API"""
        config = self.llm_config['groq']
        response = self.clients['groq'].chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "You are a material standardization expert. Return ONLY valid JSON. No explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=config['temperature'],
            max_tokens=config['max_tokens']
        )
        return self._parse_json(response.choices[0].message.content)
    
    def _call_openai(self, prompt):
        """Call OpenAI API"""
        config = self.llm_config['openai']
        response = self.clients['openai'].chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "You are a material standardization expert. Return ONLY valid JSON. No explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=config['temperature'],
            max_tokens=config['max_tokens']
        )
        return self._parse_json(response.choices[0].message.content)
    
    def _parse_json(self, text):
        """Extract JSON from response"""
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try markdown code block
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # Try any JSON object
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return None