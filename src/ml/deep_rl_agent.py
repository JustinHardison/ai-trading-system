"""
Deep Q-Network (DQN) Agent for Trading
Phase 3 upgrade - Neural network based RL
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import random

class DQN(nn.Module):
    """Deep Q-Network"""
    def __init__(self, state_size, action_size):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(state_size, 128)
        self.fc2 = nn.Linear(128, 128)
        self.fc3 = nn.Linear(128, 64)
        self.fc4 = nn.Linear(64, action_size)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = torch.relu(self.fc3(x))
        return self.fc4(x)

class DeepRLAgent:
    """
    Deep Q-Learning Agent
    Superior to Q-table for complex state spaces
    """
    
    def __init__(self, state_size=6, action_size=9):
        self.state_size = state_size
        self.action_size = action_size
        
        # Hyperparameters
        self.gamma = 0.95  # Discount factor
        self.epsilon = 1.0  # Exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.batch_size = 32
        
        # Experience replay
        self.memory = deque(maxlen=10000)
        
        # Networks
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = DQN(state_size, action_size).to(self.device)
        self.target_net = DQN(state_size, action_size).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.learning_rate)
        self.criterion = nn.MSELoss()
        
        # Action names
        self.action_names = [
            "HOLD",
            "TAKE_PROFIT_FULL",
            "SCALE_IN_50",
            "SCALE_IN_25",
            "STOP_LOSS",
            "SCALE_OUT_30",
            "SCALE_OUT_50",
            "SCALE_OUT_70",
            "TRAIL_STOP"
        ]
        
        # Stats
        self.total_decisions = 0
        self.action_counts = {i: 0 for i in range(action_size)}
        
    def get_state_vector(self, features):
        """Convert features dict to state vector"""
        return np.array([
            float(features.get('floating_profit', 0)),
            float(features.get('profit_velocity', 0)),
            float(features.get('momentum', 0)),
            float(features.get('volume_ratio', 1.0)),
            float(features.get('trend_strength', 0)),
            float(features.get('time_in_trade', 0))
        ])
    
    def get_action(self, features, training=True):
        """
        Get action using Deep Q-Network
        Returns: (action_id, action_name, confidence)
        """
        state = self.get_state_vector(features)
        
        # Epsilon-greedy
        if training and random.random() < self.epsilon:
            action = random.randrange(self.action_size)
            confidence = 50.0
        else:
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.policy_net(state_tensor)
                action = q_values.argmax().item()
                
                # Calculate confidence from Q-values
                q_vals = q_values.cpu().numpy()[0]
                exp_q = np.exp(q_vals - np.max(q_vals))
                probs = exp_q / exp_q.sum()
                confidence = probs[action] * 100
        
        self.total_decisions += 1
        self.action_counts[action] += 1
        
        return action, self.action_names[action], confidence
    
    def remember(self, state, action, reward, next_state, done):
        """Store experience in replay buffer"""
        self.memory.append((state, action, reward, next_state, done))
    
    def replay(self):
        """Train on batch from experience replay"""
        if len(self.memory) < self.batch_size:
            return
        
        # Sample batch
        batch = random.sample(self.memory, self.batch_size)
        
        states = torch.FloatTensor([x[0] for x in batch]).to(self.device)
        actions = torch.LongTensor([x[1] for x in batch]).to(self.device)
        rewards = torch.FloatTensor([x[2] for x in batch]).to(self.device)
        next_states = torch.FloatTensor([x[3] for x in batch]).to(self.device)
        dones = torch.FloatTensor([x[4] for x in batch]).to(self.device)
        
        # Current Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1))
        
        # Target Q values
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            target_q = rewards + (1 - dones) * self.gamma * next_q
        
        # Loss and optimization
        loss = self.criterion(current_q.squeeze(), target_q)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        return loss.item()
    
    def update_target_network(self):
        """Update target network with policy network weights"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
    
    def save(self, filepath='models/deep_rl_agent.pth'):
        """Save model"""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'total_decisions': self.total_decisions,
            'action_counts': self.action_counts
        }, filepath)
        
        print(f"✅ Saved Deep RL model to {filepath}")
    
    def load(self, filepath='models/deep_rl_agent.pth'):
        """Load model"""
        import os
        if not os.path.exists(filepath):
            print(f"⚠️  Model file not found: {filepath}")
            return False
        
        checkpoint = torch.load(filepath, map_location=self.device)
        
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['target_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint['epsilon']
        self.total_decisions = checkpoint['total_decisions']
        self.action_counts = checkpoint['action_counts']
        
        print(f"✅ Loaded Deep RL model from {filepath}")
        return True
