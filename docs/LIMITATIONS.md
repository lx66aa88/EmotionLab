# Limitations and intended use

- The seven outputs describe learned image categories. Facial appearance gives insufficient evidence about an individual's inner state. The uncalibrated probabilities suit course demonstration and model inspection. They are unsuitable for clinical, hiring or surveillance decisions.
- Repeated PublicTest tuning creates selection bias, and Training–PublicTest pixel duplicates weaken split independence. The historical results preserve original split membership. Final independent performance remains unverified.
- T3 epoch 56 achieved 87.0668% on Training versus 68.3477% on PublicTest at fixed weights, a gap of 18.7190 points. Accuracy rose relative to epoch 50 while validation CE and calibration error worsened. [Fixed-weight data](../results/t4_step2_analysis_20261104/data/fixed_training_vs_public.csv)
- Small and uneven classes, 48 × 48 input and capture conditions constrain results. Pose, shadows and cropping can affect the product. There is no demographic robustness validation.
- Display EMA can lag motion. Game points measure a series of thresholded game events. Their meaning is limited to the challenge.
- Historical Chrome physical-camera evidence and Safari controlled inputs cover specific scenarios. Final classroom equipment, physical network disconnection and broader OS coverage remain unverified.
