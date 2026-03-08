# RL Model: Mathematical Formulation and Architecture

## 1. Problem as an MDP

- **State** \(s_t \in \mathbb{R}^d\): At step \(t\), the state encodes history of draws \(0 \ldots t-1\).
  - **Frequency component:** \(f \in \mathbb{R}^{10000}\), normalized counts of how often each number 0000–9999 appeared in draws \(0 \ldots t-1\) (or recency-weighted).
  - **Optional sequence component:** Last \(L\) draws as multi-hot vectors, encoded by a transformer → context vector \(c \in \mathbb{R}^{d_c}\). Then \(s = [f; c]\), so \(d = 10000 + d_c\) (or \(d = 10000\) if no sequence).

- **Action** \(a_t\): Choose **K distinct numbers** from \(\{0,\ldots,9999\}\) (K = 23). So the action space is \(\binom{10000}{K}\).

- **Transition:** Deterministic given data: next state is current state updated with draw \(t\) (and optionally the new draw in the sequence buffer).

- **Reward** \(r_t\): We want the policy to maximize **expected profit per draw**.
  - **Prize-aligned reward (recommended):**  
    \(r_t = \text{(winnings from draw } t \text{)} - \text{(cost)}.\)  
    Winnings use Magnum 4D prizes (1st 2500, 2nd 1000, 3rd 500, special 180, consolation 60) RM per RM1 bet; cost = 23 RM per draw (23 numbers × RM1). So \(r_t \in [-23, +\infty)\) and the objective is \(\mathbb{E}_\pi\big[\sum_t r_t\big]\).

  - **Binary/count rewards** are surrogates; they do not match the scale of actual prizes (e.g. 1st vs consolation).

---

## 2. Policy Parameterization

- We parameterize a **distribution over the 10,000 numbers** with a neural network that outputs **logits** \(\ell \in \mathbb{R}^{10000}\).
- **Action sampling:** Sample K indices **without replacement** from \(\mathrm{Categorical}(\mathrm{softmax}(\ell))\). So
  \[
  \pi_\theta(a \mid s) \propto \prod_{i \in a} p_i, \quad p = \mathrm{softmax}(\ell(s)),
  \]
  with normalization so that exactly K indices are chosen and order does not matter for the reward (we only care which 23 numbers are chosen).

- **Log-probability** used in the policy gradient is the sum of log-probabilities of the K chosen indices under the softmax (standard REINFORCE-style approximation for subset selection).

---

## 3. Learning Objective

- **Maximize** expected return: \(J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta}\big[\sum_t r_t\big]\).
- **REINFORCE with baseline:**  
  \(\nabla_\theta J \approx \mathbb{E}\big[(r_t - b_t) \nabla_\theta \log \pi_\theta(a_t \mid s_t)\big]\), with \(b_t\) a running baseline (e.g. EMA of \(r_t\)) to reduce variance.
- **Entropy bonus:** Add \(\beta \cdot H(\pi_\theta(\cdot \mid s_t))\) to encourage exploration; we maximize \(J + \beta \sum_t H_t\).

---

## 4. Architecture Choices

### 4.1 Input–output dimensions

- **Input:** \(d = 10000\) (frequency only) or \(10000 + d_c\) (frequency + sequence context, e.g. \(d_c = 128\)).
- **Output:** 10,000 logits (one per number).

So the network does a mapping \(\mathbb{R}^d \to \mathbb{R}^{10000}\). The first layer has \(d \times h_1\) parameters; the last layer has \(h_{\mathrm{last}} \times 10000\). With \(d \approx 10^4\) and \(h \approx 256\)–512, the first and last layers dominate parameter count.

### 4.2 Depth and width

- **Depth:** 2–3 hidden layers are typical for MLP policies in RL; more depth can help with non-linear state–action structure but increases overfitting risk. We use **3 hidden layers** as a default.
- **Width:**
  - First layer: compress 10k down. A width of **512** keeps representational capacity without blowing up the first layer (10k × 512 ≈ 5M params).
  - Middle/bottleneck: **256** is a common choice and fits the “compress then predict” idea.
  - Last hidden → 10k: 256 × 10000 ≈ 2.5M params.

So we take **hidden_sizes = (512, 256, 256)**:

- Layer 0: \(d \to 512\)
- Layer 1: \(512 \to 256\)
- Layer 2: \(256 \to 256\)
- Layer 3: \(256 \to 10000\)

Total: one input layer, **3 hidden layers**, one output layer; ReLU + dropout between hidden layers.

### 4.3 Why this is “correct” for the problem

- **State:** High-dimensional (10k) but structured (normalized counts). The first layer can learn which number indices (or groups) to up/down-weight.
- **Action:** 10k-way categorical with “choose K without replacement”; the softmax + multinomial(K) is a standard and tractable choice.
- **Reward:** Using **prize-scaled reward** (winnings − cost) makes the gradient signal aligned with **profit**: hitting 1st prize improves the objective much more than hitting consolation, matching the real game.

---

## 5. Summary Table

| Component        | Choice              | Rationale |
|------------------|---------------------|-----------|
| **Reward**       | Prize (winnings − 23) | Matches profit; 1st >> special >> consolation. |
| **Hidden layers**| 3                   | Balance expressivity vs overfitting. |
| **Hidden sizes** | (512, 256, 256)     | Compress 10k → 512 → 256 → 256 → 10k; bottleneck before output. |
| **Dropout**      | 0.1                 | Slight regularization. |
| **Baseline**     | EMA of reward       | Variance reduction (REINFORCE with baseline). |
| **Entropy coef** | 0.01                | Encourage exploration. |

You can override hidden sizes via `--hidden 512,256,256` (or e.g. `1024,512,256`) and use `--reward prize` so the policy is trained to maximize actual RM profit.
