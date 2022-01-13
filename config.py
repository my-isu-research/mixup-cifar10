lr = 0.1 #learning rate
resume = False #resume from checkpoint
model = "ResNet18" #model type (default: ResNet18)
name ='0' #'name of run'
seed = 0 #type=int, help='random seed'
batch_size = 2 #type=int, help='batch size'
epoch = 2 #int, help='total epochs to run'
augment = True #help='use standard augmentation (default: True)'
decay = 1e-4 #type=float, help='weight decay'
alpha =1. #type=float, help='mixup interpolation coefficient (default: 1)')
dataset = "../../Datasets/Kvasir - Aziz"  #type=str, help='Folder containing the dataset')
iterations = 3 #type=int, help='Number of experiments to run')
