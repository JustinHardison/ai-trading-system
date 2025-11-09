#!/usr/bin/env python3
"""
DQN AGENT TRAINING
Deep Q-Network for intelligent position management
"""

import os
import sys
import numpy as np
import joblib
from collections import deque
import random

class DQNAgent:
    """
    Deep Q-Network agent for position management
    
    State: [p&l_pct, age_minutes, entry_conviction, current_conviction, 
            m5_structure, m15_structure, m30_structure, h1_structure,
            volatility, momentum, portfolio_risk]
    
    Actions: [HOLD, ADD, PARTIAL_CLOSE, CLOSE_ALL]
    """
    
    def __init__(self, state_size=11, action_size=4):
        self.state_size = state_size
        self.action_size = action_size
        
        # Hyperparameters
        self.gamma = 0.95  # Discount factor
        self.epsilon = 1.0  # Exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        
        # Experience replay
        self.memory = deque(maxlen=10000)
        self.batch_size = 32
        
        # Q-table (simplified for Mac/Wine compatibility)
        # Instead of neural network, use discretized Q-table
        self.q_table = {}
        
        print("="*80)
        print("DQN AGENT INITIALIZED")
        print("="*80)
        print(f"State size: {state_size}")
        print(f"Action size: {action_size}")
        print(f"Actions: HOLD(0), ADD(1), PARTIAL_CLOSE(2), CLOSE_ALL(3)")
        print("="*80)
    
    def discretize_state(self, state):
        """Convert continuous state to discrete for Q-table"""
        # Discretize each state variable into bins
        discrete = []
        
        # P&L: -5% to +5% in 0.5% bins
        discrete.append(int((state[0] + 5) / 0.5))
        
        # Age: 0-300 min in 10 min bins
        discrete.append(int(state[1] / 10))
        
        # Convictions: 0-100 in 10 point bins
        discrete.append(int(state[2] / 10))
        discrete.append(int(state[3] / 10))
        
        # Structures: 0-100 in 20 point bins
        for i in range(4, 8):
            discrete.append(int(state[i] / 20))
        
        # Volatility, Momentum, Risk: 0-100 in 20 point bins
        for i in range(8, 11):
            discrete.append(int(state[i] / 20))
        
        return tuple(discrete)
    
    def remember(self, state, action, reward, next_state, done):
        """Store experience in replay memory"""
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state):
        """Choose action using epsilon-greedy policy"""
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        
        discrete_state = self.discretize_state(state)
        
        if discrete_state not in self.q_table:
            self.q_table[discrete_state] = np.zeros(self.action_size)
        
        return np.argmax(self.q_table[discrete_state])
    
    def replay(self):
        """Train on batch of experiences"""
        if len(self.memory) < self.batch_size:
            return
        
        minibatch = random.sample(self.memory, self.batch_size)
        
        for state, action, reward, next_state, done in minibatch:
            discrete_state = self.discretize_state(state)
            discrete_next_state = self.discretize_state(next_state)
            
            if discrete_state not in self.q_table:
                self.q_table[discrete_state] = np.zeros(self.action_size)
            if discrete_next_state not in self.q_table:
                self.q_table[discrete_next_state] = np.zeros(self.action_size)
            
            target = reward
            if not done:
                target = reward + self.gamma * np.amax(self.q_table[discrete_next_state])
            
            self.q_table[discrete_state][action] = target
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def save(self, filepath):
        """Save agent to file"""
        agent_data = {
            'q_table': dict(self.q_table),
            'epsilon': self.epsilon,
            'state_size': self.state_size,
            'action_size': self.action_size
        }
        joblib.dump(agent_data, filepath)
        print(f"✅ Agent saved: {filepath}")
    
    def load(self, filepath):
        """Load agent from file"""
        agent_data = joblib.load(filepath)
        self.q_table = agent_data['q_table']
        self.epsilon = agent_data['epsilon']
        print(f"✅ Agent loaded: {filepath}")

def train_dqn_agent():
    """Train DQN agent"""
    print("="*80)
    print("DQN AGENT TRAINING")
    print("="*80)
    
    agent = DQNAgent()
    
    # Simulate training episodes
    # In production, this will learn from live trades
    print("\n📊 Simulating training episodes...")
    print("   (In production, agent will learn from live trades)")
    
    episodes = 100
    
    for episode in range(episodes):
        # Simulate position lifecycle
        state = np.random.rand(11) * 100  # Random initial state
        done = False
        total_reward = 0
        steps = 0
        
        while not done and steps < 50:
            # Choose action
            action = agent.act(state)
            
            # Simulate reward
            # In production, this comes from actual trade results
            if action == 0:  # HOLD
                reward = np.random.randn() * 0.1  # Small random reward
            elif action == 1:  # ADD
                reward = np.random.randn() * 0.5  # Medium risk/reward
            elif action == 2:  # PARTIAL_CLOSE
                reward = np.random.randn() * 0.3  # Moderate reward
            else:  # CLOSE_ALL
                reward = np.random.randn() * 0.8  # High impact
                done = True
            
            # Simulate next state
            next_state = state + np.random.randn(11) * 5
            next_state = np.clip(next_state, 0, 100)
            
            # Remember and learn
            agent.remember(state, action, reward, next_state, done)
            agent.replay()
            
            state = next_state
            total_reward += reward
            steps += 1
        
        if episode % 10 == 0:
            print(f"Episode {episode}/{episodes} - Reward: {total_reward:.2f} - Epsilon: {agent.epsilon:.3f}")
    
    # Save agent
    model_path = "/Users/justinhardison/ai-trading-system/models/dqn_agent.pkl"
    agent.save(model_path)
    
    print("\n" + "="*80)
    print("✅ DQN AGENT TRAINING COMPLETE")
    print("="*80)
    print(f"Q-table size: {len(agent.q_table)} states")
    print(f"Epsilon: {agent.epsilon:.3f}")
    print(f"Model saved: {model_path}")
    print("\n📝 NOTE: Agent will continue learning from live trades")
    print("="*80)

if __name__ == "__main__":
    train_dqn_agent()
