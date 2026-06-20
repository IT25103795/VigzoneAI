import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import string
import json
import argparse
import os
import sys


# ==========================================
# CLASS 1: The Robust Sequence Preprocessor
# ==========================================
class VigzoneSequenceVocab:
    def __init__(self):
        self.word2idx = {"<PAD>": 0, "<UNK>": 1}
        self.idx2word = {0: "<PAD>", 1: "<UNK>"}
        self.idx = 2

    def clean_text(self, text):
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        return text.split()

    def build_vocab(self, text):
        words = self.clean_text(text)
        for word in words:
            if word not in self.word2idx:
                self.word2idx[word] = self.idx
                self.idx2word[self.idx] = word
                self.idx += 1

    def encode(self, text):
        words = self.clean_text(text)
        return torch.tensor(
            [self.word2idx.get(w, 1) for w in words],
            dtype=torch.long,
        )

    def decode(self, indices):
        return " ".join(self.idx2word.get(i.item(), "<UNK>") for i in indices)

    def save(self, path):
        data = {"word2idx": self.word2idx, "idx2word": {str(k): v for k, v in self.idx2word.items()}, "idx": self.idx}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        vocab = cls()
        vocab.word2idx = data["word2idx"]
        vocab.idx2word = {int(k): v for k, v in data["idx2word"].items()}
        vocab.idx = data["idx"]
        return vocab

    @property
    def size(self):
        return len(self.word2idx)


# ==========================================
# CLASS 2: LSTM Attention-Enhanced Brain
# ==========================================
class VigzoneAttentionModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim=64, hidden_dim=128, num_layers=2, dropout=0.2):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embedding_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attention = nn.Linear(hidden_dim, 1)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, hidden=None):
        embedded = self.dropout(self.embedding(x))
        out, hidden = self.lstm(embedded, hidden)
        attn_scores = self.attention(out)
        attn_weights = F.softmax(attn_scores, dim=1)
        context = out * attn_weights
        logits = self.fc(self.dropout(context.contiguous().view(-1, self.hidden_dim)))
        return logits, hidden, attn_weights

    def init_hidden(self, batch_size=1):
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim)
        return (h0, c0)


# ==========================================
# CHECKPOINT SAVE / LOAD
# ==========================================
CHECKPOINT_PATH = "vigzone_checkpoint.pth"
VOCAB_PATH = "vigzone_vocab.json"

MODEL_CONFIG = {
    "embedding_dim": 32,
    "hidden_dim": 64,
    "num_layers": 2,
    "dropout": 0.1,
}


def save_checkpoint(model, vocab, path=CHECKPOINT_PATH):
    torch.save({
        "model_state": model.state_dict(),
        "config": MODEL_CONFIG,
        "vocab_size": vocab.size,
    }, path)
    vocab.save(VOCAB_PATH)
    print(f"Checkpoint saved to {path}")
    print(f"Vocabulary saved to {VOCAB_PATH}")


def load_checkpoint(path=CHECKPOINT_PATH):
    if not os.path.exists(path) or not os.path.exists(VOCAB_PATH):
        print("No saved checkpoint found. Train the model first with: python main.py train")
        sys.exit(1)

    vocab = VigzoneSequenceVocab.load(VOCAB_PATH)
    checkpoint = torch.load(path, weights_only=True)
    config = checkpoint["config"]
    model = VigzoneAttentionModel(
        vocab_size=checkpoint["vocab_size"],
        embedding_dim=config["embedding_dim"],
        hidden_dim=config["hidden_dim"],
        num_layers=config["num_layers"],
        dropout=config["dropout"],
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, vocab


# ==========================================
# TRAINING
# ==========================================
def train_model(epochs=300, lr=0.005):
    try:
        with open("dataset.txt", "r", encoding="utf-8") as f:
            training_text = f.read()
    except FileNotFoundError:
        print("ERROR: dataset.txt not found. Place your training data in dataset.txt")
        sys.exit(1)

    vocab = VigzoneSequenceVocab()
    vocab.build_vocab(training_text)

    encoded = vocab.encode(training_text)
    if len(encoded) < 2:
        print("ERROR: dataset.txt needs more words to create sequences.")
        sys.exit(1)

    inputs = encoded[:-1].unsqueeze(0)
    targets = encoded[1:]

    model = VigzoneAttentionModel(vocab_size=vocab.size, **MODEL_CONFIG)
    loss_fn = nn.CrossEntropyLoss(ignore_index=0)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=100, gamma=0.5)

    print(f"Vocabulary size: {vocab.size} words")
    print(f"Sequence length: {len(encoded)} tokens")
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"\nTraining Vigzone AI ({epochs} epochs)...\n")

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        hidden = model.init_hidden()
        predictions, _, _ = model(inputs, hidden)
        loss = loss_fn(predictions, targets)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()
        scheduler.step()

        if (epoch + 1) % 50 == 0 or epoch == 0:
            print(f"  Epoch {epoch + 1:>4}/{epochs} | Loss: {loss.item():.4f} | LR: {scheduler.get_last_lr()[0]:.6f}")

    print("\nTraining complete!")
    save_checkpoint(model, vocab)
    return model, vocab


# ==========================================
# TEXT GENERATION
# ==========================================
def generate(model, vocab, prompt, length=30, temperature=0.7, top_k=10):
    model.eval()
    words = vocab.clean_text(prompt)
    if not words:
        words = [list(vocab.word2idx.keys())[2]]

    token_ids = [vocab.word2idx.get(w, 1) for w in words]
    generated = list(words)
    hidden = model.init_hidden()

    with torch.no_grad():
        if len(token_ids) > 1:
            context_input = torch.tensor([token_ids[:-1]])
            _, hidden, _ = model(context_input, hidden)

        current_id = torch.tensor([[token_ids[-1]]])

        for _ in range(length):
            logits, hidden, _ = model(current_id, hidden)
            last_logits = logits[-1] / temperature

            if top_k > 0:
                top_values, top_indices = torch.topk(last_logits, min(top_k, last_logits.size(-1)))
                filtered = torch.full_like(last_logits, float('-inf'))
                filtered.scatter_(0, top_indices, top_values)
                last_logits = filtered

            probs = F.softmax(last_logits, dim=-1)
            predicted_id = torch.multinomial(probs, num_samples=1).item()
            predicted_word = vocab.idx2word.get(predicted_id, "<UNK>")

            if predicted_word not in ("<UNK>", "<PAD>"):
                generated.append(predicted_word)

            current_id = torch.tensor([[predicted_id]])

    return " ".join(generated)


# ==========================================
# INTERACTIVE MODE
# ==========================================
def interactive_mode():
    model, vocab = load_checkpoint()
    temperature = 0.7
    length = 30
    top_k = 10

    print("\n" + "=" * 50)
    print("  Vigzone AI - Interactive Mode")
    print("=" * 50)
    print(f"  Temperature: {temperature}  |  Length: {length}  |  Top-K: {top_k}")
    print("  Commands: temp <val>, length <val>, topk <val>, quit")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if user_input.lower().startswith("temp "):
            try:
                temperature = max(0.1, min(2.0, float(user_input.split()[1])))
                print(f"  Temperature set to {temperature}")
            except (ValueError, IndexError):
                print("  Usage: temp <0.1-2.0>")
            continue

        if user_input.lower().startswith("length "):
            try:
                length = max(5, min(100, int(user_input.split()[1])))
                print(f"  Length set to {length}")
            except (ValueError, IndexError):
                print("  Usage: length <5-100>")
            continue

        if user_input.lower().startswith("topk "):
            try:
                top_k = max(1, min(50, int(user_input.split()[1])))
                print(f"  Top-K set to {top_k}")
            except (ValueError, IndexError):
                print("  Usage: topk <1-50>")
            continue

        output = generate(model, vocab, user_input, length=length, temperature=temperature, top_k=top_k)
        print(f"AI  > {output}\n")


# ==========================================
# CLI ENTRY POINT
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Vigzone AI - Text Generation Engine")
    subparsers = parser.add_subparsers(dest="command")

    train_parser = subparsers.add_parser("train", help="Train the model on dataset.txt")
    train_parser.add_argument("--epochs", type=int, default=300, help="Number of training epochs")
    train_parser.add_argument("--lr", type=float, default=0.005, help="Learning rate")

    gen_parser = subparsers.add_parser("generate", help="Generate text from a prompt")
    gen_parser.add_argument("--prompt", type=str, default="code", help="Starting word(s)")
    gen_parser.add_argument("--length", type=int, default=30, help="Number of words to generate")
    gen_parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    gen_parser.add_argument("--top-k", type=int, default=10, help="Top-K filtering")

    subparsers.add_parser("interactive", help="Interactive generation mode")

    args = parser.parse_args()

    if args.command == "train":
        train_model(epochs=args.epochs, lr=args.lr)

    elif args.command == "generate":
        model, vocab = load_checkpoint()
        output = generate(model, vocab, args.prompt, length=args.length, temperature=args.temperature, top_k=args.top_k)
        print(f"\nPrompt: '{args.prompt}'")
        print(f"Output: {output}")

    elif args.command == "interactive":
        interactive_mode()

    else:
        print("=" * 50)
        print("  Vigzone AI - Text Generation Engine")
        print("=" * 50 + "\n")

        model, vocab = train_model()

        print("\n--- Generation Demo ---\n")
        for prompt in ["machine learning", "clean code", "neural networks"]:
            output = generate(model, vocab, prompt, length=20)
            print(f"  '{prompt}' -> {output}\n")


if __name__ == "__main__":
    main()
