# Loads Customer 1's Year 1 clean data using dataset.py.
# Passes those clean daily windows into your model.py.
# Runs the canonical 5-step PyTorch training loop 
# Saves the trained model weights into Step 2/checkpoints/local_autoencoder_c1.pt so we can use it to catch hackers!

import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Import our previous milestones!
from dataset import load_customer_data, SmartMeterDataset
from model import Conv1DAutoencoder

def train_local_model(customer_id: int = 1, epochs: int = 15, batch_size: int = 16, lr: float = 0.001):
    print(f"=====================================================")
    print(f" TRAINING LOCAL AUTOENCODER FOR CUSTOMER {customer_id}")
    print(f"=====================================================")

    # 1. Load Parquet Data (Filtered for Customer 1)
    parquet_path = "Step 1/DATA/ausgrid_solar_attacked.parquet"
    df_customer = load_customer_data(parquet_path, customer_id=customer_id)

    # 2. Extract Phase 1 (Clean Baseline Year 1: Days 0 to 364)
    df_phase_1 = df_customer[df_customer["attack_phase"] == "1_NORMAL"].copy()
    
    # 3. Create Dataset & DataLoader (365 daily windows of 48 intervals)
    train_dataset = SmartMeterDataset(df_phase_1, window_size=48, stride=48)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    print(f"Training on {len(train_dataset)} clean 24-hour windows over {epochs} epochs.\n")

    # 4. Instantiate Model, Loss Function, and Optimizer
    model = Conv1DAutoencoder(in_channels=2)
    criterion = nn.MSELoss()  # Autoencoders minimize difference between input & reconstruction
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # 5. Training Loop
    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0

        for batch_windows, _ in train_loader:
            optimizer.zero_grad()
            reconstructed = model(batch_windows)
            loss = criterion(reconstructed, batch_windows)
            loss.backward()
            optimizer.step()
            # Step 1: Clear old gradients using optimizer.zero_grad()
            # Step 2: Reconstruct the batch: reconstructed = model(batch_windows)
            # Step 3: Compute reconstruction error: loss = criterion(reconstructed, batch_windows)
            # Step 4: Backpropagate gradients: loss.backward()
            # Step 5: Update model weights: optimizer.step()
            # -------------------------------------------------------------
            
            # >>> FILL IN THE 5 LINES HERE <<<

            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        print(f"Epoch [{epoch:02d}/{epochs:02d}] --- Reconstruction MSE Loss: {avg_loss:.5f}")

    # 6. Save the Trained Weights
    os.makedirs("Step 2/checkpoints", exist_ok=True)
    checkpoint_path = f"Step 2/checkpoints/local_autoencoder_c{customer_id}.pt"
    torch.save(model.state_dict(), checkpoint_path)
    print(f"\n✅ Training Complete! Model weights saved to: {checkpoint_path}")

    return model, train_dataset.get_scaler()


if __name__ == "__main__":
    train_local_model(customer_id=1, epochs=15)