# Advanced DQN Agent Training

## Overview

This is a **standalone** Deep Q-Network (DQN) agent for position management. It does NOT affect the current trading system until explicitly integrated.

## What It Does

The DQN agent learns optimal position management by:
1. **Observing** all 173 market features + position state
2. **Learning** from historical trades what actions led to best outcomes
3. **Deciding** whether to HOLD, CLOSE, SCALE_OUT, or ADD to positions

## Architecture

### State Space (180 dimensions)
- **173 market features**: RSI, MACD, trends, support/resistance, volume, etc.
- **7 position features**: profit %, peak profit, age, lot size, type, DCA count, giveback

### Action Space (9 actions)
1. `HOLD` - Do nothing
2. `CLOSE_ALL` - Close entire position
3. `SCALE_OUT_25` - Take 25% profit
4. `SCALE_OUT_50` - Take 50% profit
5. `SCALE_OUT_75` - Take 75% profit
6. `SCALE_IN_25` - Add 25% to winner
7. `SCALE_IN_50` - Add 50% to winner
8. `DCA_25` - Average down 25%
9. `DCA_50` - Average down 50%

### Neural Network
```
Input (180) 
  → Dense(256) + ReLU + Dropout(0.2)
  → Dense(128) + ReLU + Dropout(0.2)
  → Dense(64) + ReLU + Dropout(0.1)
  → Dense(32) + ReLU
  → Output(9) [Q-values for each action]
```

## Training Process

### 1. Data Requirements

The agent needs historical trade data with:
- All 173 market features
- Position states (profit, age, etc.)
- Outcomes (final profit/loss)

**Data sources:**
- MT5 exported CSV files (`*training_data*.csv`)
- API logs (parsed)
- Historical trade database

**Expected location:**
```
/Users/justinhardison/Library/Application Support/
  net.metaquotes.wine.metatrader5/drive_c/Program Files/
  MetaTrader 5/MQL5/Files/*training_data*.csv
```

### 2. Training Command

```bash
cd /Users/justinhardison/ai-trading-system
python3 train_dqn_agent.py
```

### 3. Training Parameters

```python
learning_rate = 0.0001      # How fast it learns
gamma = 0.95                # How much it values future rewards
epsilon_start = 1.0         # Initial exploration (100%)
epsilon_end = 0.01          # Final exploration (1%)
epsilon_decay = 0.995       # Exploration decay rate
memory_size = 50000         # Experience replay buffer
batch_size = 64             # Training batch size
num_epochs = 100            # Training iterations
```

### 4. Training Output

```
models/dqn_checkpoint_epoch_10.pt
models/dqn_checkpoint_epoch_20.pt
...
models/advanced_dqn_agent_final.pt  ← Final trained model
```

## How It Learns

### Experience Replay
```python
# Agent stores experiences:
(state, action, reward, next_state, done)

# Examples:
(profit=0.5%, H1_trend=0.7, ..., HOLD, +0.1%, next_state, False)
(profit=1.2%, H1_trend=0.3, ..., SCALE_OUT_50, +0.6%, next_state, False)
(profit=-0.8%, recovery=0.8, ..., DCA_25, +0.3%, next_state, False)
```

### Q-Learning
```python
# For each state, learn Q-values (expected rewards) for each action:
Q(state, HOLD) = 0.5
Q(state, CLOSE_ALL) = 0.3
Q(state, SCALE_OUT_50) = 0.8  ← Best action!

# Agent picks action with highest Q-value
```

### Reward Function
```python
# Reward = outcome of the action
# Positive: Action led to profit
# Negative: Action led to loss

# Examples:
HOLD when trend continuing → +reward
CLOSE_ALL when trend reversing → +reward
SCALE_OUT_50 at peak → +reward
DCA when recovery high → +reward
```

## Validation

After training, the agent is validated on:
1. **Action distribution**: Does it use all actions appropriately?
2. **Performance**: Does it beat random actions?
3. **Comparison**: Does it beat current EV Exit Manager?

## Integration (NOT YET DONE)

Once trained and validated, integration would look like:

```python
# In api.py (FUTURE - not implemented yet)
if use_dqn_agent:
    state = dqn_agent.extract_state(context, position_data)
    action_idx = dqn_agent.select_action(state, training=False)
    action = dqn_agent.get_action_name(action_idx)
    
    if action == 'CLOSE_ALL':
        return {'should_exit': True, 'reason': 'DQN: Close all'}
    elif action == 'SCALE_OUT_50':
        return {'should_exit': True, 'action': 'SCALE_OUT', 'pct': 0.5}
    # ... etc
```

## Current Status

- ✅ Agent architecture built
- ✅ Training script created
- ⏳ Needs historical data
- ⏳ Needs training (100 epochs)
- ⏳ Needs validation
- ❌ NOT integrated into live system

## Next Steps

1. **Prepare training data**
   - Export historical trades from MT5
   - Ensure all 173 features are included
   - Format as CSV files

2. **Train the agent**
   ```bash
   python3 train_dqn_agent.py
   ```

3. **Validate performance**
   - Compare to random actions
   - Compare to current EV Exit Manager
   - Backtest on historical data

4. **Integration decision**
   - If DQN beats current system → integrate
   - If DQN underperforms → retrain or abandon
   - If DQN similar → use as backup/validation

## Files Created

```
src/ai/advanced_dqn_agent.py     ← DQN agent class
train_dqn_agent.py               ← Training script
DQN_TRAINING_README.md           ← This file
```

## Safety

- **Standalone**: Does not affect current trading system
- **Isolated**: Trains separately
- **Validated**: Must prove performance before integration
- **Reversible**: Can be removed without affecting current system

## Questions?

This is a complete, production-ready DQN agent architecture. It just needs:
1. Historical data to train on
2. Training time (few hours)
3. Validation results
4. Decision to integrate or not

**The current system continues to work unchanged.**
