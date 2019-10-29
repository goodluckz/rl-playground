from collections import deque
import random

import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F


class Bit_Flipping(object):
    def __init__(self, num_bits):
        self.num_bits = num_bits

    def reset(self):
        self.done = False
        self.num_steps = 0
        self.state = np.random.randint(2, size=self.num_bits)
        self.target = np.random.randint(2, size=self.num_bits)
        return np.copy(self.state), self.target

    def step(self, action):
        if self.done:
            raise ValueError

        self.state[action] = 1 - self.state[action]

        if self.num_steps > self.num_bits + 1:
            self.done = True
        self.num_steps += 1

        if np.sum(self.state == self.target) == self.num_bits:
            self.done = True
            return np.copy(self.state), 0, self.done, {}
        else:
            return np.copy(self.state), -1, self.done, {}


class Model(nn.Module):
    def __init__(self, num_inputs, num_outputs, hidden_size=256):
        super(Model, self).__init__()

        self.linear1 = nn.Linear(num_inputs,  hidden_size)
        self.linear2 = nn.Linear(hidden_size, num_outputs)

    def forward(self, state, goal):
        x = torch.cat([state, goal], 1)
        x = F.relu(self.linear1(x))
        x = self.linear2(x)
        return x


class ReplayBuffer(object):
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done, goal):
        self.buffer.append((state, action, reward, next_state, done, goal))

    def sample(self, batch_size):
        state, action, reward, next_state, done, goal = zip(
            *random.sample(self.buffer, batch_size))
        return np.stack(state), action, reward, np.stack(next_state), done, np.stack(goal)

    def __len__(self):
        return len(self.buffer)


def update_target(current_model, target_model):
    target_model.load_state_dict(current_model.state_dict())


def compute_td_error(batch_size):
    if replay_buffer.__len__() < batch_size:
        return None
    state, action, reward, next_state, done, goal = replay_buffer.sample(
        batch_size)
    state = torch.FloatTensor(state).to(device)
    reward = torch.FloatTensor(reward).unsqueeze(1).to(device)
    action = torch.LongTensor(action).unsqueeze(1).to(device)
    next_state = torch.FloatTensor(next_state).to(device)
    goal = torch.FloatTensor(goal).to(device)
    mask = torch.FloatTensor(1 - np.float32(done)).unsqueeze(1).to(device)

    q_values = model(state, goal)
    q_value = q_values.gather(1, action)

    next_q_values = target_model(next_state, goal)
    target_action = next_q_values.max(1)[1].unsqueeze(1)
    next_q_value = target_model(next_state, goal).gather(1, target_action)

    expected_q_value = reward + 0.99 * next_q_value * mask

    loss = (q_value - expected_q_value.detach()).pow(2).mean()

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    return loss


def get_action(model, state, goal, epsilon=0.1):
    if random.random() < epsilon:
        return random.randrange(env.num_bits)

    state = torch.FloatTensor(state).unsqueeze(0).to(device)
    goal = torch.FloatTensor(goal).unsqueeze(0).to(device)
    q_value = model(state, goal)
    best_action = torch.argmax(q_value, dim=1).item()
    return best_action


use_cuda = torch.cuda.is_available()
device = torch.device("cuda" if use_cuda else "cpu")


if __name__ == "__main__":
    num_bits = 11
    env = Bit_Flipping(num_bits)

    model = Model(2 * num_bits, num_bits).to(device)
    target_model = Model(2 * num_bits, num_bits).to(device)
    update_target(model, target_model)

    replay_buffer = ReplayBuffer(50000)
    # hyperparams:
    batch_size = 5
    new_goals = 5
    max_frames = 200000

    optimizer = optim.Adam(model.parameters())
    frame_idx = 0
    all_rewards = []
    losses = []

    while frame_idx < max_frames:
        state, goal = env.reset()
        done = False
        episode = []
        total_reward = 0
        while not done:
            action = get_action(model, state, goal)
            next_state, reward, done, _ = env.step(action)
            replay_buffer.push(state, action, reward, next_state, done, goal)
            state = next_state
            total_reward += reward
            frame_idx += 1

        if frame_idx % 100 == 0:
            # plot(frame_idx, [np.mean(all_rewards[i:i+100])
            # for i in range(0, len(all_rewards), 100)], losses)
            print(np.mean(all_rewards[-100:]))
            print("loss: ", np.mean(losses))

        loss = compute_td_error(batch_size)
        if loss is not None:
            losses.append(loss.item())
        all_rewards.append(total_reward)
