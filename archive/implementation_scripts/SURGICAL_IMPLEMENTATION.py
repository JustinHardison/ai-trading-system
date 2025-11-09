#!/usr/bin/env python3
"""
SURGICAL IMPLEMENTATION - Careful, tested changes
Add functionality without breaking existing code
"""

import os
import re

def add_global_variables():
    """Add dqn_agent to global variables"""
    api_file = "/Users/justinhardison/ai-trading-system/api.py"
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    # Add dqn_agent after ppo_agent
    if "dqn_agent = None" not in content:
        content = content.replace(
            "ppo_agent = None  # Will be loaded after training completes",
            "ppo_agent = None  # Will be loaded after training completes\ndqn_agent = None  # DQN RL agent\nposition_manager = None  # Position manager"
        )
        
        # Update global declaration in startup
        content = content.replace(
            "global ml_models, feature_engineer, trade_manager, ppo_agent, adaptive_optimizer, ai_risk_manager, position_manager",
            "global ml_models, feature_engineer, trade_manager, ppo_agent, adaptive_optimizer, ai_risk_manager, position_manager, dqn_agent"
        )
    
    with open(api_file, 'w') as f:
        f.write(content)
    
    print("✅ Added global variables")
    return True


def add_dqn_loading():
    """Add DQN agent loading in startup"""
    api_file = "/Users/justinhardison/ai-trading-system/api.py"
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    dqn_code = '''
    # 6. Load DQN RL Agent
    try:
        dqn_agent_path = '/Users/justinhardison/ai-trading-system/models/dqn_agent.pkl'
        if os.path.exists(dqn_agent_path):
            dqn_agent = joblib.load(dqn_agent_path)
            q_table_size = len(dqn_agent.get('q_table', {})) if isinstance(dqn_agent, dict) else 0
            logger.info(f"✅ DQN RL Agent loaded: {q_table_size} states learned")
        else:
            logger.warning("⚠️  DQN agent not found - using heuristics")
            dqn_agent = None
    except Exception as e:
        logger.error(f"❌ Failed to load DQN agent: {e}")
        dqn_agent = None
'''
    
    # Insert before "logger.info("═══..." SYSTEM READY section
    marker = '    logger.info("═══════════════════════════════════════════════════════════════════")\n    logger.info("SYSTEM READY")'
    if marker in content and "Load DQN RL Agent" not in content:
        content = content.replace(marker, dqn_code + "\n" + marker)
    
    with open(api_file, 'w') as f:
        f.write(content)
    
    print("✅ Added DQN loading")
    return True


def add_helper_functions():
    """Add conviction scoring and weight adjustment functions"""
    api_file = "/Users/justinhardison/ai-trading-system/api.py"
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    functions = '''

# ═══════════════════════════════════════════════════════════════════
# CONVICTION SCORING & TIMEFRAME WEIGHTING
# ═══════════════════════════════════════════════════════════════════

def calculate_conviction(ml_confidence: float, structure_score: float, 
                        volume_score: float = 50, momentum_score: float = 50) -> float:
    """Calculate overall conviction score (0-100)"""
    conviction = (
        ml_confidence * 0.40 +
        structure_score * 0.30 +
        volume_score * 0.15 +
        momentum_score * 0.15
    )
    return min(max(conviction, 0), 100)


def adjust_timeframe_weights(trigger_timeframe: str) -> dict:
    """Dynamically adjust timeframe weights based on trigger"""
    base_weights = {
        'M5': 0.10, 'M15': 0.15, 'M30': 0.20,
        'H1': 0.25, 'H4': 0.20, 'D1': 0.10
    }
    
    adjusted = base_weights.copy()
    if trigger_timeframe in adjusted:
        adjusted[trigger_timeframe] *= 1.5
        total = sum(adjusted.values())
        for tf in adjusted:
            adjusted[tf] /= total
    
    return adjusted


'''
    
    # Insert before HELPER FUNCTIONS section
    marker = "# ═══════════════════════════════════════════════════════════════════\n# HELPER FUNCTIONS"
    if marker in content and "def calculate_conviction" not in content:
        content = content.replace(marker, functions + marker)
    
    with open(api_file, 'w') as f:
        f.write(content)
    
    print("✅ Added helper functions")
    return True


def test_syntax():
    """Test if API has valid syntax"""
    import ast
    
    try:
        with open('/Users/justinhardison/ai-trading-system/api.py', 'r') as f:
            code = f.read()
        ast.parse(code)
        print("✅ API syntax is valid")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error at line {e.lineno}: {e.msg}")
        return False


if __name__ == "__main__":
    print("="*80)
    print("SURGICAL IMPLEMENTATION - STEP BY STEP")
    print("="*80)
    
    steps = [
        ("Adding global variables", add_global_variables),
        ("Adding DQN loading", add_dqn_loading),
        ("Adding helper functions", add_helper_functions),
        ("Testing syntax", test_syntax),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        if not step_func():
            print(f"❌ Failed at: {step_name}")
            exit(1)
    
    print("\n" + "="*80)
    print("✅ PHASE 1 COMPLETE - Core functions added")
    print("="*80)
    print("\nNext: Integrate into decision flow (Phase 2)")
