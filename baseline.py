import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
import torch.nn.functional as F
import torch.backends.cudnn as cudnn
import torchvision
import torchvision.transforms as transforms
import os
import time
import argparse
import numpy as np
import json

import imdbfolder_train_val_combined as imdbfolder
import config_task
from models import resnet, base
import sgd
from utils import *

import matplotlib
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description='PyTorch Residual Adapters training')
parser.add_argument('--dataset', default='imagenet12', nargs='+', help='Task(s) to be trained')
parser.add_argument('--wd', default=5., type=float, help='weight decay for the classification layer')
parser.add_argument('--wd3x3', default=1., type=float, nargs='+', help='weight decay for the 3x3')
parser.add_argument('--factor', default='1.', type=float, help='Width factor of the network')

parser.add_argument('--nb_epochs', default=120, type=int, help='nb epochs')
parser.add_argument('--lr', default=0.1, type=float, help='initial learning rate')

parser.add_argument('--datadir', default='../data/decathlon-1.0/', help='folder containing data folder')
parser.add_argument('--imdbdir', default='../data/decathlon-1.0/annotations/', help='annotation folder')
parser.add_argument('--ckpdir', default='./pretrained_model_on_train_and_val/', help='folder saving checkpoint')

parser.add_argument('--seed', default=0, type=int, help='seed')
parser.add_argument('--step1', default=80, type=int, help='nb epochs before first lr decrease')
parser.add_argument('--step2', default=100, type=int, help='nb epochs before second lr decrease')
args = parser.parse_args()

'''
if type(args.dataset) is str:
    pretrained_model_dir = args.ckpdir + args.dataset
    if not os.path.isdir(pretrained_model_dir):
    	os.mkdir(pretrained_model_dir)
    args.dataset = [args.dataset]

if type(args.wd3x3) is float:
    args.wd3x3 = [args.wd3x3]

config_task.decay3x3 = np.array(args.wd3x3) * 0.0001
config_task.factor = args.factor
args.wd = args.wd *  0.0001
'''
f = pretrained_model_dir + "/params.json"
with open(f, 'wb') as fh:
    json.dump(vars(args), fh)     

start_epoch = 0
def train(epoch, train_loaders, net, net_optimizer):
    #Train the model
    net.train()
    total_step = len(train_loaders[0])
    tasks_top1 = dict()
    tasks_losses = dict()

    for task_id in range(len(train_loaders)):
        tasks_top1[task_id] = AverageMeter()
        tasks_losses[task_id] = AverageMeter() 

    for i, data_pair in MinibatchScheduler(train_loaders):
       for task_id, task_batch in enumerate(data_pair):
            images = task_batch[0] 
            labels = task_batch[1]    
 
            if use_cuda:
                images, labels = images.cuda(async=True), labels.cuda(async=True)
            images, labels = Variable(images), Variable(labels)

            outputs = net.forward(images, task_id)
            _, predicted = torch.max(outputs.data, 1)
            correct = predicted.eq(labels.data).cpu().sum()
            tasks_top1[task_id].update(correct.item()*100 / (labels.size(0)+0.0), labels.size(0))
        
            # Loss
            loss = criterion(outputs, labels)
            tasks_losses[task_id].update(loss.data[0], labels.size(0))

            if i % 50 == 0:
                print ("Epoch [{}/{}], Step [{}/{}], Task {} Loss: {:.4f}, Acc Val: {:.4f}, Acc Avg: {:.4f}"
                    .format(epoch+1, args.nb_epochs, i+1, total_step, task_id, tasks_losses[task_id].val, tasks_top1[task_id].val, tasks_top1[task_id].avg))

            #---------------------------------------------------------------------#
            # Backward and optimize
            net_optimizer.zero_grad()
            loss.backward()  
            net_optimizer.step()
            
    return [tasks_top1[i].avg for i in range(len(train_loaders))], [tasks_losses[i].avg for i in range(len(train_loaders))]

def test(epoch, val_loaders, net, best_acc):
    net.eval()

    tasks_top1 = dict()
    tasks_losses = dict()

    for task_id in range(len(val_loaders)):
        tasks_top1[task_id] = AverageMeter()
        tasks_losses[task_id] = AverageMeter() 

    # Test the model
    with torch.no_grad():
        for task_id, val_loader in enumerate(val_loaders):
            for i, (images, labels) in enumerate(val_loader):
                if use_cuda:
                    images, labels = images.cuda(async=True), labels.cuda(async=True)
                images, labels = Variable(images), Variable(labels)

                outputs = net.forward(images, task_id)
                _, predicted = torch.max(outputs.data, 1)
                correct = predicted.eq(labels.data).cpu().sum()
                tasks_top1[task_id].update(correct.item()*100 / (labels.size(0)+0.0), labels.size(0))
            
                # Loss
                loss = criterion(outputs, labels)
                tasks_losses[task_id].update(loss.data[0], labels.size(0))           

    print "test accuracy"
    for task_id in range(len(val_loaders)):        
        print ("Epoch [{}/{}], Task {} Loss: {:.4f}, Acc Val: {:.4f}, Acc Avg: {:.4f}"
            .format(epoch+1, args.nb_epochs, task_id, tasks_losses[task_id].avg, tasks_top1[task_id].val, tasks_top1[task_id].avg))

    acc = np.sum([tasks_top1[i].avg for i in range(len(val_loaders))])

    # Save checkpoint.
    if acc > best_acc:
        print('Saving..')
        state = {
            'net': net,
            'acc': acc,
            'epoch': epoch,
        }
        torch.save(state, pretrained_model_dir +'/' + args.dataset[0] + '.t7')
        best_acc = acc
    
    return [tasks_top1[i].avg for i in range(len(val_loaders))], [tasks_losses[i].avg for i in range(len(val_loaders))], best_acc
'''
#####################################
# Prepare data loaders
#train_loaders, val_loaders, num_classes = imdbfolder.prepare_data_loaders(args.dataset, args.datadir, args.imdbdir, True)
#results = np.zeros((4,start_epoch+args.nb_epochs, len(num_classes)))

# Create the network
'''
net = get_model('Resnet26', [1000], 'imagenet12', mode='train')
weight =  net._modules['conv1']._modules['depthwise'][0].weight.cpu().data.numpy()
print weight.shape
plt.imshow(weight[:,0,:,:])
plt.savefig("test.png")

'''
model_parameters = filter(lambda p: p.requires_grad, net.parameters())
params = sum([np.prod(p.size()) for p in model_parameters])
print "params number"
print params

np.random.seed(args.seed)
use_cuda = torch.cuda.is_available()
if use_cuda:
    net.cuda()
    cudnn.benchmark = True
    #net = nn.DataParallel(net)

# Loss and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = sgd.SGD(filter(lambda p: p.requires_grad, net.parameters()), lr= args.lr, momentum=0.9, weight_decay= args.wd)

best_acc = 0.0  # best test accuracy
for epoch in range(start_epoch, start_epoch+args.nb_epochs):
    adjust_learning_rate_and_learning_taks(optimizer, epoch, args)
    st_time = time.time()
    # Training and validation
    train_acc, train_loss = train(epoch, train_loaders, net, optimizer)
    test_acc, test_loss, best_acc = test(epoch, val_loaders, net, best_acc)
    # Record statistics
    for i in range(len(args.dataset)):
        results[0:2,epoch,i] = [train_loss[i], train_acc[i]]
   
    for i in range(len(args.dataset)):
        results[2:4,epoch,i] = [test_loss[i],test_acc[i]]
    np.save(pretrained_model_dir + '/results', results)
    print('Epoch lasted {0}'.format(time.time()-st_time))
'''