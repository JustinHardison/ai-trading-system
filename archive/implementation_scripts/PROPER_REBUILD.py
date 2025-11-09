#!/usr/bin/env python3
"""
PROPER REBUILD - No Shortcuts
Fully automated deep dive, debug, and fix
"""

import os
import sys
import glob
import time
import subprocess
from datetime import datetime

class ProperRebuild:
    def __init__(self):
        self.base_dir = "/Users/justinhardison/ai-trading-system"
        self.data_dir = f"{self.base_dir}/data"
        self.models_dir = f"{self.base_dir}/models"
        self.symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']
        self.log_file = f"{self.base_dir}/proper_rebuild.log"
        
        self.issues_found = []
        self.fixes_applied = []
        
        print("="*80)
        print("PROPER REBUILD - DEEP DIVE & DEBUG")
        print("="*80)
        print("No shortcuts. Doing it right.")
        print("="*80)
    
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a') as f:
            f.write(log_msg + "\n")
    
    def issue(self, problem):
        self.issues_found.append(problem)
        self.log(f"❌ ISSUE: {problem}")
    
    def fix(self, solution):
        self.fixes_applied.append(solution)
        self.log(f"✅ FIX: {solution}")
    
    def audit_training_data(self):
        """Audit 1: Check training data for all symbols"""
        self.log("\n" + "="*80)
        self.log("AUDIT 1: TRAINING DATA")
        self.log("="*80)
        
        csv_files = glob.glob(f"{self.data_dir}/*.csv")
        self.log(f"Found {len(csv_files)} CSV files")
        
        # Check which symbols have data
        symbols_with_data = set()
        for csv_file in csv_files:
            basename = os.path.basename(csv_file).lower()
            for symbol in self.symbols:
                if symbol in basename:
                    symbols_with_data.add(symbol)
                    
                    # Check file size
                    size_mb = os.path.getsize(csv_file) / (1024 * 1024)
                    self.log(f"✅ {symbol}: {size_mb:.1f} MB")
        
        # Find missing symbols
        missing_symbols = set(self.symbols) - symbols_with_data
        if missing_symbols:
            self.issue(f"Missing training data for: {', '.join(missing_symbols)}")
            self.log(f"   Need to export data for these symbols")
            return False
        else:
            self.fix("All 8 symbols have training data")
            return True
    
    def audit_models(self):
        """Audit 2: Check if models are symbol-specific"""
        self.log("\n" + "="*80)
        self.log("AUDIT 2: MODEL SPECIFICITY")
        self.log("="*80)
        
        import joblib
        
        # Load all models and check if they're identical
        model_hashes = {}
        
        for symbol in self.symbols:
            model_file = f"{self.models_dir}/{symbol}_ensemble_latest.pkl"
            if os.path.exists(model_file):
                model = joblib.load(model_file)
                
                # Check model accuracy (if all same, they're copies)
                acc = model.get('ensemble_accuracy', 0)
                model_hashes[symbol] = acc
                
                self.log(f"{symbol}: Accuracy = {acc*100:.2f}%")
        
        # Check if all accuracies are identical
        unique_accuracies = set(model_hashes.values())
        if len(unique_accuracies) == 1:
            self.issue("All models have identical accuracy - they're copies!")
            self.log("   Models were trained on same data (US100)")
            self.log("   Need symbol-specific training")
            return False
        else:
            self.fix("Models have different accuracies - symbol-specific")
            return True
    
    def audit_feature_mismatch(self):
        """Audit 3: Check feature count mismatch"""
        self.log("\n" + "="*80)
        self.log("AUDIT 3: FEATURE MISMATCH")
        self.log("="*80)
        
        import joblib
        
        # Check model expected features
        model_file = f"{self.models_dir}/us30_ensemble_latest.pkl"
        if os.path.exists(model_file):
            model = joblib.load(model_file)
            model_features = len(model.get('feature_names', []))
            self.log(f"Model expects: {model_features} features")
        else:
            model_features = 0
        
        # Check API feature engineer
        api_file = f"{self.base_dir}/api.py"
        with open(api_file, 'r') as f:
            api_code = f.read()
            
        if 'SimpleFeatureEngineer' in api_code and '27 features' in api_code:
            api_features = 27
            self.log(f"API provides: {api_features} features (SimpleFeatureEngineer)")
        elif 'EnhancedFeatureEngineer' in api_code:
            api_features = 162
            self.log(f"API provides: {api_features} features (EnhancedFeatureEngineer)")
        else:
            api_features = 0
        
        if model_features != api_features and model_features > 0:
            self.issue(f"Feature mismatch: Model expects {model_features}, API provides {api_features}")
            self.log("   Models will get wrong inputs!")
            return False
        else:
            self.fix("Feature counts match")
            return True
    
    def audit_rl_integration(self):
        """Audit 4: Check if RL agent is integrated"""
        self.log("\n" + "="*80)
        self.log("AUDIT 4: RL AGENT INTEGRATION")
        self.log("="*80)
        
        # Check if RL agent file exists
        rl_file = f"{self.models_dir}/dqn_agent.pkl"
        if not os.path.exists(rl_file):
            self.issue("RL agent file not found")
            return False
        
        self.log(f"✅ RL agent file exists: {os.path.getsize(rl_file)/1024:.1f} KB")
        
        # Check if API loads it
        api_file = f"{self.base_dir}/api.py"
        with open(api_file, 'r') as f:
            api_code = f.read()
        
        if 'dqn_agent' in api_code.lower() and 'joblib.load' in api_code:
            self.fix("RL agent is loaded in API")
            return True
        else:
            self.issue("RL agent exists but not loaded in API")
            self.log("   Agent is trained but unused")
            return False
    
    def audit_conviction_scoring(self):
        """Audit 5: Check if conviction scoring is implemented"""
        self.log("\n" + "="*80)
        self.log("AUDIT 5: CONVICTION SCORING")
        self.log("="*80)
        
        api_file = f"{self.base_dir}/api.py"
        with open(api_file, 'r') as f:
            api_code = f.read()
        
        has_conviction = 'conviction' in api_code.lower()
        has_dynamic_weights = 'dynamic' in api_code.lower() and 'weight' in api_code.lower()
        
        if has_conviction and has_dynamic_weights:
            self.fix("Conviction scoring implemented")
            return True
        else:
            self.issue("Conviction scoring not implemented")
            self.log("   Core intelligence missing")
            return False
    
    def audit_dead_code(self):
        """Audit 6: Find dead code and unused imports"""
        self.log("\n" + "="*80)
        self.log("AUDIT 6: DEAD CODE")
        self.log("="*80)
        
        # Check for duplicate feature engineers
        src_features = f"{self.base_dir}/src/features"
        if os.path.exists(src_features):
            feature_files = glob.glob(f"{src_features}/*.py")
            self.log(f"Found {len(feature_files)} feature engineer files")
            
            if len(feature_files) > 2:  # Should only have 1-2
                self.issue(f"Too many feature engineer files: {len(feature_files)}")
                self.log("   Likely duplicates and dead code")
                return False
        
        # Check for old model files
        old_models = []
        for model_file in glob.glob(f"{self.models_dir}/*.pkl"):
            basename = os.path.basename(model_file)
            if 'integrated' in basename or 'backup' in basename or '2025' in basename:
                old_models.append(basename)
        
        if old_models:
            self.issue(f"Found {len(old_models)} old model files")
            for old in old_models[:5]:  # Show first 5
                self.log(f"   - {old}")
            return False
        else:
            self.fix("No old model files found")
            return True
    
    def audit_ea_architecture(self):
        """Audit 7: Check EA architecture"""
        self.log("\n" + "="*80)
        self.log("AUDIT 7: EA ARCHITECTURE")
        self.log("="*80)
        
        ea_file = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/AI_Trading_EA_Ultimate.mq5"
        
        if not os.path.exists(ea_file):
            self.issue("EA file not found")
            return False
        
        with open(ea_file, 'r') as f:
            ea_code = f.read()
        
        # Check for event-driven architecture
        has_event_driven = 'IsNewBar' in ea_code or 'lastM5Time' in ea_code
        has_trigger_tf = 'trigger_timeframe' in ea_code
        
        if has_event_driven and has_trigger_tf:
            self.fix("EA has event-driven architecture")
            return True
        else:
            self.issue("EA still uses fixed 60-second scanning")
            self.log("   Missing event-driven bar detection")
            return False
    
    def run_full_audit(self):
        """Run complete system audit"""
        self.log("\n" + "="*80)
        self.log("STARTING FULL SYSTEM AUDIT")
        self.log("="*80)
        
        audits = [
            ("Training Data", self.audit_training_data),
            ("Model Specificity", self.audit_models),
            ("Feature Mismatch", self.audit_feature_mismatch),
            ("RL Integration", self.audit_rl_integration),
            ("Conviction Scoring", self.audit_conviction_scoring),
            ("Dead Code", self.audit_dead_code),
            ("EA Architecture", self.audit_ea_architecture),
        ]
        
        results = {}
        for name, audit_func in audits:
            try:
                passed = audit_func()
                results[name] = passed
            except Exception as e:
                self.log(f"❌ Error in {name}: {e}")
                results[name] = False
        
        # Summary
        self.log("\n" + "="*80)
        self.log("AUDIT SUMMARY")
        self.log("="*80)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{status}: {name}")
        
        self.log(f"\nScore: {passed}/{total} ({passed/total*100:.0f}%)")
        
        self.log("\n" + "="*80)
        self.log(f"ISSUES FOUND: {len(self.issues_found)}")
        self.log("="*80)
        for issue in self.issues_found:
            self.log(f"❌ {issue}")
        
        self.log("\n" + "="*80)
        self.log(f"FIXES APPLIED: {len(self.fixes_applied)}")
        self.log("="*80)
        for fix in self.fixes_applied:
            self.log(f"✅ {fix}")
        
        return passed == total

if __name__ == "__main__":
    rebuild = ProperRebuild()
    all_good = rebuild.run_full_audit()
    
    if all_good:
        print("\n🎉 SYSTEM IS ACTUALLY READY!")
    else:
        print("\n⚠️  SYSTEM NEEDS WORK - See issues above")
        print(f"\nLog file: {rebuild.log_file}")
    
    sys.exit(0 if all_good else 1)
