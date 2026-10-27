import os
import json
import re
import yaml
import asyncio
import aiohttp

class LLMHandler:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.llm_config = self.config.get('llm', {})
        self.available_provider = None
        self.api_key = None
        self.model = None
        self._init_providers()
    
    def _init_providers(self):
        groq_conf = self.llm_config.get('groq', {})
        if groq_conf.get('enabled', False):
            api_key = os.getenv(groq_conf.get('api_key_env', 'GROQ_API_KEY'))
            if api_key:
                self.api_key = api_key
                self.model = groq_conf.get('model', 'openai/gpt-oss-20b')
                self.available_provider = 'groq'
                print("✅ Groq Async LLM initialized")
                return
        
        openai_conf = self.llm_config.get('openai', {})
        if openai_conf.get('enabled', False):
            api_key = os.getenv(openai_conf.get('api_key_env', 'OPENAI_API_KEY'))
            if api_key:
                self.api_key = api_key
                self.model = openai_conf.get('model', 'gpt-4o-mini')
                self.available_provider = 'openai'
                print("✅ OpenAI Async LLM initialized")
                return
        
        print("⚠️ No LLM keys found. Using rule-based fallback.")
    
    def is_available(self): return self.available_provider is not None
    def get_provider_name(self): return self.available_provider or "rule_based"
    
    def _build_prompt(self, name, mat_type, sub_type, uom, is_asset):
        if is_asset:
            return f"""You are an ERP Asset Expert. Format: CATEGORY-TYPE-BRAND-MODEL-ID.
Asset: {name} | Type: {mat_type} | Subtype: {sub_type}
Return ONLY JSON: {{"standardized_name": "STRING", "asset_type": "STRING", "asset_subtype": "STRING", "hsn_code": "STRING", "confidence": 95}}"""
        else:
            return f"""You are an ERP Material Expert. Format: CATEGORY-SUBCATEGORY-SIZE-SPEC.
Material: {name} | Type: {mat_type} | Subtype: {sub_type} | UOM: {uom}
Return ONLY JSON: {{"standardized_name": "STRING", "material_type": "STRING", "material_subtype": "STRING", "hsn_code": "STRING", "uom": "STRING", "confidence": 95}}"""

    async def _async_call(self, session, prompt, retry_count=2):
        url = "https://api.groq.com/openai/v1/chat/completions" if self.available_provider == 'groq' else "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return ONLY valid JSON format. No markdown, no explanations."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        for attempt in range(retry_count):
            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        return self._parse_json(content)
                    elif response.status == 429:
                        # Rate limit hit - wait and retry
                        await asyncio.sleep(2) 
                        continue
                    else:
                        return None
            except Exception:
                await asyncio.sleep(1)
                continue
        return None

    def standardize_batch(self, batch_data):
        """Processes a batch of rows concurrently using asyncio"""
        async def run_batch():
            # Added timeout so it doesn't hang forever
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = []
                for item in batch_data:
                    prompt = self._build_prompt(item['name'], item['mat_type'], item['sub_type'], item['uom'], item['is_asset'])
                    tasks.append(self._async_call(session, prompt))
                return await asyncio.gather(*tasks)
        
        try:
            return asyncio.run(run_batch())
        except Exception as e:
            print(f"Async Batch Error: {e}")
            return [None] * len(batch_data)

    def _parse_json(self, text):
        try: return json.loads(text)
        except: pass
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(1))
            except: pass
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group())
            except: pass
        return None