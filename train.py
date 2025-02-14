#!/usr/bin/env python3 -u
# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in
# the root directory of this source tree.
# from __future__ import print_function

import argparse
import csv
import os
import torchvision.models as trained_models

import numpy as np
import torch
from torch.autograd import Variable
import torch.backends.cudnn as cudnn
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision

import models
from utils import progress_bar

from first import *
import pandas as pd
import sys

import config as args


def main():
    best_acc = 0  # best test accuracy
    start_epoch = 0  # start from epoch 0 or last checkpoint epoch

    def mixup_data(x, y, alpha=1.0, use_cuda=True):
        '''Returns mixed inputs, pairs of targets, and lambda'''
        if alpha > 0:
            lam = np.random.beta(alpha, alpha)
        else:
            lam = 1

        batch_size = x.size()[0]
        if use_cuda:
            index = torch.randperm(batch_size).cuda()
        else:
            index = torch.randperm(batch_size)

        mixed_x = lam * x + (1 - lam) * x[index, :]
        y_a, y_b = y, y[index]
        return mixed_x, y_a, y_b, lam


    def mixup_criterion(criterion, pred, y_a, y_b, lam):
        return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


    def train(epoch):
        print('\nEpoch: %d' % epoch)
        net.train()
        train_loss = 0
        reg_loss = 0
        correct = 0
        total = 0
        for batch_idx, (inputs, targets) in enumerate(trainloader):
            if use_cuda:
                inputs, targets = inputs.cuda(), targets.cuda()

            inputs, targets_a, targets_b, lam = mixup_data(inputs, targets,
                                                           args.alpha, use_cuda)
            inputs, targets_a, targets_b = map(Variable, (inputs,
                                                          targets_a, targets_b))
            outputs = net(inputs)
            loss = mixup_criterion(criterion, outputs, targets_a, targets_b, lam)
            train_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += targets.size(0)
            correct += (lam * predicted.eq(targets_a.data).cpu().sum().float()
                        + (1 - lam) * predicted.eq(targets_b.data).cpu().sum().float())

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            progress_bar(batch_idx, len(trainloader),
                         'Loss: %.3f | Reg: %.5f | Acc: %.3f%% (%d/%d)'
                         % (train_loss/(batch_idx+1), reg_loss/(batch_idx+1),
                            100.*correct/total, correct, total))
        return (train_loss/batch_idx, reg_loss/batch_idx, 100.*correct/total)


    def test(epoch, best_acc):
        net.eval()
        test_loss = 0
        correct = 0
        total = 0
        for batch_idx, (inputs, targets) in enumerate(testloader):
            if use_cuda:
                inputs, targets = inputs.cuda(), targets.cuda()
            inputs, targets = Variable(inputs, volatile=True), Variable(targets)
            outputs = net(inputs)
            loss = criterion(outputs, targets)

            test_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += targets.size(0)
            correct += predicted.eq(targets.data).cpu().sum()

            progress_bar(batch_idx, len(testloader),
                         'Loss: %.3f | Acc: %.3f%% (%d/%d)'
                         % (test_loss/(batch_idx+1), 100.*correct/total,
                            correct, total))
        acc = 100.*correct/total
        if epoch == start_epoch + args.epoch - 1 or acc > best_acc:
            checkpoint(acc, epoch)
        if acc > best_acc:
            best_acc = acc
        return (test_loss/batch_idx, 100.*correct/total, best_acc)


    def checkpoint(acc, epoch):
        # Save checkpoint.
        print('Saving..')
        state = {
            'net': net,
            'acc': acc,
            'epoch': epoch,
            'rng_state': torch.get_rng_state()
        }
        if not os.path.isdir('checkpoint'):
            os.mkdir('checkpoint')
        torch.save(state, './checkpoint/ckpt.t7' + args.name + '_'
                   + str(args.seed))


    def adjust_learning_rate(optimizer, epoch):
        """decrease the learning rate at 100 and 150 epoch"""
        lr = args.lr
        if epoch >= 100:
            lr /= 10
        if epoch >= 150:
            lr /= 10
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr


    use_cuda = torch.cuda.is_available()
    result_df = pd.DataFrame(columns = ['Test_Acc', 'Test, Pre', 'Test_Re', 'Test_F1', 'Train_Acc',
    'Train_Pre', 'Train_Re', 'Train_F1'])

    for iter in range(args.iterations):

        best_acc = 0  # best test accuracy
        start_epoch = 0  # start from epoch 0 or last checkpoint epoch

        if args.seed != 0:
            torch.manual_seed(args.seed)

        # Data
        print('==> Preparing data..')
        if args.augment:
            transform_train = transforms.Compose([
                transforms.RandomCrop(224, padding=4),
                transforms.RandomHorizontalFlip(),
                transforms.ToTensor(),
                transforms.Normalize((0.4914, 0.4822, 0.4465),
                                     (0.2023, 0.1994, 0.2010)),
            ])
        else:
            transform_train = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize((0.4914, 0.4822, 0.4465),
                                     (0.2023, 0.1994, 0.2010)),
            ])


        transform_test = transforms.Compose([
            transforms.RandomCrop(224, padding=4),
            transforms.ToTensor(),
            transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
        ])

        dataset = args.dataset
        trainset = datasets.ImageFolder(os.path.join(dataset, 'train'),
                                                      transform_train)
        trainloader = torch.utils.data.DataLoader(trainset,
                                                  batch_size=args.batch_size,
                                                  shuffle=True, num_workers=8)
        testset = datasets.ImageFolder(os.path.join(dataset, 'test'),
                                                      transform_test)
        testloader = torch.utils.data.DataLoader(testset, batch_size=args.batch_size,
                                                 shuffle=False, num_workers=8)

        # Model
        if args.resume:
            # Load checkpoint.
            print('==> Resuming from checkpoint..')
            assert os.path.isdir('checkpoint'), 'Error: no checkpoint directory found!'
            checkpoint = torch.load('./checkpoint/ckpt.t7' + args.name + '_'
                                    + str(args.seed))
            net = checkpoint['net']
            best_acc = checkpoint['acc']
            start_epoch = checkpoint['epoch'] + 1
            rng_state = checkpoint['rng_state']
            torch.set_rng_state(rng_state)
        else:
            print('==> Building model..')
            # net = models.__dict__[args.model]()
            net = trained_models.resnet18(pretrained = True)
            num_ftrs = net.fc.in_features
            net.fc = nn.Linear(num_ftrs, len(testset.classes))
            net = torch.nn.DataParallel(net).cuda()

        if not os.path.isdir('results'):
            os.mkdir('results')
        logname = ('results/log_' + net.__class__.__name__ + '_' + args.name + '_'
                   + str(args.seed) + '.csv')

        if use_cuda:
            net.cuda()
            net = torch.nn.DataParallel(net)
            print(torch.cuda.device_count())
            cudnn.benchmark = True
            print('Using CUDA..')

        criterion = nn.CrossEntropyLoss()
        optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=0.9,
                              weight_decay=args.decay)


        if not os.path.exists(logname):
            with open(logname, 'w') as logfile:
                logwriter = csv.writer(logfile, delimiter=',')
                logwriter.writerow(['epoch', 'train loss', 'reg loss', 'train acc',
                                    'test loss', 'test acc'])

        for epoch in range(start_epoch, args.epoch):
            train_loss, reg_loss, train_acc = train(epoch)
            test_loss, test_acc, best_acc = test(epoch, best_acc)
            adjust_learning_rate(optimizer, epoch)
            with open(logname, 'a') as logfile:
                logwriter = csv.writer(logfile, delimiter=',')
                logwriter.writerow([epoch, train_loss, reg_loss, train_acc, test_loss,
                                    test_acc])

        trainset, trainloader, testset, testloader = get_loaders_and_dataset(dataset, transform_train, transform_test, args.batch_size)
        targets, preds, _ = make_prediction(net, testset.classes, testloader)
        test_class_report = classification_report(targets, preds, target_names=testset.classes)
        test_metrics = get_metrics_from_classi_report(test_class_report)

        targets, preds, _ = make_prediction(net, testset.classes, trainloader)
        train_class_report = classification_report(targets, preds, target_names=testset.classes)
        train_metrics = get_metrics_from_classi_report(train_class_report)

        print(test_metrics)
        metrics = []
        metrics.extend(test_metrics)
        metrics.extend(train_metrics)
        result_df.loc[len(result_df.index)] = metrics
        result_df.to_csv('experimental_results_for_mixup.csv')


if __name__ == "__main__":
    main()
