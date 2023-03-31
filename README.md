# NCI-DOE-Collab-Pilot1-Unified-Drug-Response-Multi-tasking-Predictor

### Description
The Pilot 1 Unified Drug Response Predictor multi-tasking, also called UnoMT, shows how to train and use a neural network model to predict drug dose response, cell line classification, etc. across multiple data sources. This method is based on UNO implemented in PyTorch.

### User Community
Primary: Cancer biology data modeling</br>
Secondary: Machine Learning; Bioinformatics; Computational Biology

### Usability
To use the untrained model, users must be familiar with processing and feature extraction of molecular drug data, gene expression, and training of neural networks. The input to the model is preprocessed data. Users should have extended experience with preprocessing this data.

### Uniqueness
The community can use a neural network and multiple machine learning techniques to perform multi-tasks such as predict drug response cell line classification. The general rule is that classical methods like random forests would perform better for small datasets, while neural network approaches like UnoMT would perform better for relatively larger datasets.

### Components
The following components are in the Model and Data Clearinghouse (MoDaC):
* The [Pilot 1 Cancer Drug Response Prediction Multi-tasking Dataset](https://modac.cancer.gov/searchTab?dme_data_id=NCI-DME-MS01-8088592) asset contains the processed training and test data. 

### Technical Details
Refer to this [README](./Pilot1/UnoMT/README.md).
