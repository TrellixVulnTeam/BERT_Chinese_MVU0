import torch
from BERT import BertConfig, BertForFullSequenceRelevance

model_state_dict = torch.load("../Pretrained/pytorch_model.bin")

# CPU Test
model = BertForFullSequenceRelevance.from_pretrained("../Pretrained/", state_dict=model_state_dict, device="cpu")
model.eval()
q_input_ids = torch.LongTensor([[31, 51, 99], [15, 5, 0]])
p_input_ids = torch.LongTensor([[31, 51, 99], [15, 5, 0]])
loss = model(p_input_ids, q_input_ids, labels=True)
print("loss: ", loss)
scores = model(p_input_ids, q_input_ids)
print("scores: ", scores)

# GPU Test
model = BertForFullSequenceRelevance.from_pretrained("../Pretrained/", state_dict=model_state_dict, device="cuda")
model.to("cuda")
model.eval()
q_input_ids = torch.LongTensor([[31, 51, 99], [15, 5, 0]]).to("cuda")
p_input_ids = torch.LongTensor([[31, 51, 99], [15, 5, 0]]).to("cuda")
loss = model(p_input_ids, q_input_ids, labels=True)
print("loss: ", loss.detach().cpu().numpy())
scores = model(p_input_ids, q_input_ids)
print("scores: ", scores.detach().cpu().numpy())