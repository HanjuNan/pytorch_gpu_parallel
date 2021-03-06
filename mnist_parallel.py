import time
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import StepLR
from torch.nn.parallel import DataParallel

torch.manual_seed(0)
torch.cuda.manual_seed_all(0)


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.dropout = nn.Dropout(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.fc2(x)
        x = F.log_softmax(x)

        return x


def train(args, model, device, train_loader, optimizer, epoch):
    model.train()
    for idx, (images, targets) in enumerate(train_loader):
        images, targets = images.to(device), targets.to(device)
        pred = model(images)
        loss = F.cross_entropy(pred, targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if idx % args.log_interval == 0:
            print("Train Time:{}, epoch: {}, step: {}, loss: {}".format(time.strftime("%Y-%m-%d%H:%M:%S"), epoch + 1, idx, loss.item()))


def mytest(args, model, device, test_loader):
    model.eval()
    test_loss = 0
    test_acc = 0

    with torch.no_grad():
        for (images, targets) in test_loader:
            images, targets = images.to(device), targets.to(device)
            pred = model(images)
            loss = F.cross_entropy(pred, targets, reduction="sum")
            test_loss += loss.item()
            pred_label = torch.argmax(pred, dim=1, keepdims=True)
            test_acc += pred_label.eq(targets.view_as(pred_label)).sum().item()

    test_loss /= len(test_loader.dataset)
    test_acc /= len(test_loader.dataset)

    print("Test Time:{}, loss: {}, acc: {}".format(time.strftime("%Y-%m-%d%H:%M:%S"), test_loss, test_acc))


def main():
    parser = argparse.ArgumentParser(description="MNIST TRAINING")
    parser.add_argument('--device_ids', type=str, default='0', help="Training Devices,example: '0,1,2'")
    parser.add_argument('--epochs', type=int, default=30, help="Training Epoch")
    parser.add_argument('--log_interval', type=int, default=100, help="Log Interval")

    args = parser.parse_args()

    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307), (0.3081))])

    dataset_train = datasets.MNIST('./data', train=True, transform=transform,download=True)
    dataset_test = datasets.MNIST('./data', train=False, transform=transform,download=True)

    train_loader = DataLoader(dataset_train, batch_size=32, shuffle=True, num_workers=8)
    test_loader = DataLoader(dataset_test, batch_size=32, shuffle=False, num_workers=8)

    device_ids = list(map(int,args.device_ids.split(",")))
    # ???GPU
    device = torch.device('cuda:{}'.format(device_ids[0]))
    # print("device = ",device)
    # print("type(device) = ",type(device))
    model = Net().to(device)
    # output_device:?????????GPU????????????????????????device(???GPU)???
    model = DataParallel(model,device_ids=device_ids,output_device=device)

    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    scheduler = StepLR(optimizer, step_size=1)

    for epoch in range(args.epochs):
        train(args, model, device, train_loader, optimizer, epoch)
        mytest(args, model, device, test_loader)
        scheduler.step()
        torch.save(model.state_dict(), 'train.pt')

if __name__ == '__main__':
    main()


# Train Time:2021-12-1013:23:19, epoch: 1, step: 0, loss: 2.294469118118286
# Test Time:2021-12-1013:39:37, loss: 0.061310396361351015, acc: 0.9819
# 39-23 = 16