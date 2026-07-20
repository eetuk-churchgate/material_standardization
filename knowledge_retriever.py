"""
DYNAMIC KNOWLEDGE RETRIEVER
Uses RAG (Retrieval-Augmented Generation) to find similar standardized items
from uploaded master data. Zero hardcoding.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from fuzzywuzzy import fuzz
import json
import pickle

class KnowledgeRetriever:
    """Retrieves similar items from master data using embeddings + fuzzy matching"""
    
    def __init__(self, master_file_path=None):
        self.master_data = None
        self.embeddings = None
        self.model = None
        self.material_map = {}
        self.asset_map = {}
        
        if master_file_path and Path(master_file_path).exists():
            self.load_master_data(master_file_path)
    
    def load_master_data(self, file_path):
        """Load and index the standardized master data"""
        print(f"📚 Loading master data from: {file_path}")
        
        # Read all sheets
        xl = pd.ExcelFile(file_path)
        dfs = {}
        for sheet in xl.sheet_names:
            dfs[sheet] = pd.read_excel(file_path, sheet_name=sheet)
        
        # Combine all sheets
        all_data = []
        for sheet_name, df in dfs.items():
            df['source_sheet'] = sheet_name
            all_data.append(df)
        
        self.master_data = pd.concat(all_data, ignore_index=True)
        
        # Build lookup maps
        self._build_lookup_maps()
        
        # Generate embeddings for semantic search
        self._generate_embeddings()
        
        print(f"✅ Loaded {len(self.master_data)} standardized items")
        return self.master_data
    
    def _build_lookup_maps(self):
        """Build efficient lookup dictionaries"""
        for idx, row in self.master_data.iterrows():
            # Detect standardized name column
            std_name_col = None
            for col in ['Standardized_Name', 'Standardized_Asset_Name', 'Standardized_Material_Name']:
                if col in row.index and pd.notna(row[col]):
                    std_name_col = col
                    break
            
            if std_name_col:
                key = row[std_name_col].upper()
                self.material_map[key] = row.to_dict()
            
            # Also index by old name if available
            for col in ['Old_Material_Name', 'Original_Name', 'MaterialName']:
                if col in row.index and pd.notna(row[col]):
                    self.material_map[row[col].upper()] = row.to_dict()
                    break
    
    def _generate_embeddings(self):
        """Generate sentence embeddings for semantic search"""
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Get all names to embed
            names = []
            for idx, row in self.master_data.iterrows():
                name = ""
                for col in ['Standardized_Name', 'Standardized_Asset_Name', 'MaterialName', 'Original_Name']:
                    if col in row.index and pd.notna(row[col]):
                        name = str(row[col])
                        break
                names.append(name)
            
            self.master_data['search_text'] = names
            self.embeddings = self.model.encode(names, show_progress_bar=False)
            
            print(f"✅ Generated embeddings for {len(names)} items")
            
        except Exception as e:
            print(f"⚠️ Could not load embedding model: {e}")
            print("⚠️ Falling back to fuzzy matching only")
            self.model = None
            self.embeddings = None
    
    def search_similar(self, query, top_k=5):
        """Search for similar items in master data"""
        results = []
        
        # 1. Exact match
        exact = self._exact_match(query)
        if exact:
            return [exact]
        
        # 2. Fuzzy match
        fuzzy_results = self._fuzzy_match(query, top_k)
        results.extend(fuzzy_results)
        
        # 3. Semantic search (if embeddings available)
        if self.model and self.embeddings is not None:
            semantic_results = self._semantic_search(query, top_k)
            results.extend(semantic_results)
        
        # Deduplicate and sort by score
        seen = set()
        unique_results = []
        for r in sorted(results, key=lambda x: x.get('score', 0), reverse=True):
            key = r.get('standardized_name', '')
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        
        return unique_results[:top_k]
    
    def _exact_match(self, query):
        """Try exact match first"""
        query_upper = query.upper().strip()
        if query_upper in self.material_map:
            return {
                'score': 100,
                'standardized_name': self.material_map[query_upper].get('Standardized_Name', 
                                    self.material_map[query_upper].get('Standardized_Asset_Name', '')),
                'source': 'exact_match',
                'master_row': self.material_map[query_upper]
            }
        return None
    
    def _fuzzy_match(self, query, top_k=5):
        """Fuzzy string matching"""
        results = []
        query_upper = query.upper().strip()
        
        for key, value in self.material_map.items():
            score = fuzz.token_sort_ratio(query_upper, key)
            if score > 60:  # Threshold
                results.append({
                    'score': score,
                    'standardized_name': value.get('Standardized_Name', 
                                        value.get('Standardized_Asset_Name', key)),
                    'source': 'fuzzy_match',
                    'master_row': value
                })
        
        return sorted(results, key=lambda x: x['score'], reverse=True)[:top_k]
    
    def _semantic_search(self, query, top_k=5):
        """Semantic search using embeddings"""
        if self.model is None or self.embeddings is None:
            return []
        
        query_embedding = self.model.encode([query])
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.5:  # Threshold
                row = self.master_data.iloc[idx]
                results.append({
                    'score': float(similarities[idx] * 100),
                    'standardized_name': row.get('Standardized_Name', 
                                        row.get('Standardized_Asset_Name', '')),
                    'source': 'semantic_search',
                    'master_row': row.to_dict()
                })
        
        return results
    
    def get_best_match(self, query):
        """Get single best match with confidence"""
        results = self.search_similar(query, top_k=3)
        if results:
            best = results[0]
            return {
                'standardized_name': best['standardized_name'],
                'confidence': best['score'],
                'source': best['source'],
                'alternatives': results[1:] if len(results) > 1 else []
            }
        return None
    
    def save_index(self, path="data/index.pkl"):
        """Save the indexed knowledge base"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'material_map': self.material_map,
                'asset_map': self.asset_map
            }, f)
    
    def load_index(self, path="data/index.pkl"):
        """Load saved index"""
        if Path(path).exists():
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.material_map = data.get('material_map', {})
                self.asset_map = data.get('asset_map', {})
            return True
        return False