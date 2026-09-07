# Speaker Notes

## Slide 01

Hello everyone, the paper we introduce today is SwingBot. SwingBot can learn physical features from in-hand tactile exploration and do a dynamic swing-up task.

## Slide 02

We will introduce this work in detail in the four sections as follow.

## Slide 03

翻页

## Slide 04

So, why do we focus on the swinging-up dynamic task? Dynamic task is very common in our daily life. Many of you may spent time spinning pen when you are in middle school. Actually, this is a pretty hard dynamic task. To do a dynamic task successfully, we need to estimate some key physical factors including mass ,center of mass, friction, and moment of inertia. The estimation needs to be accurate, otherwise, a small estimation error may lead to (catastrophic) large differences in results.
So the problem that we want to solve is : How can robots develop an accurate estimation of these mechanical properties?

## Slide 05

To answer this question,let's think about how we humans understand the physical world. We intuitively understand how objects behave—not through exact physics equations, but through implicit learning by interacting with the environment.
For example, we naturally use more effort to toss a small lead ball than a large volleyball—without calculating mass, density or computing complex formulas.
Our physical understanding comes from multiple senses: vision, sound, and touch. Among them, tactile experience provides one of the richest physical information, like when a kungfu master try to adapt to a new weapon, they do not perform a series of measurements on it. Instead, by using it, they develop an estimation of its characteristics.
So this inspires us to build a similar tactile-based “physical intuition” embedding.

## Slide 06

This table shows the related works and their limitations: as I said before, many previous work only considers Static/Quasi-Static case, like fetching or holding an object.
Manually engineered models are not ML-based, and they do not utilize tactile information. So they are lack of generalization.
There are also some previous works on intuition physics, but they are restricted to vision modal. Also some key factors are very hard to measure by vision, like friction and forces, because the noise is too large for those factors. For example, the resolution is too low to precisely tell what is happening on the contact surfaces.
So it is hard to measure the forces and the physical properties of the surfaces by only vision. In contrast, in-hand manipulation with tactile sensing provides richer and more direct feedback about contact interactions. This enables accurate estimation of these physical parameters.

## Slide 08

Here is an overview of the workflow of Swingbot.
The key of this method is two types of manually designed exploraion actions, that is, tilting and shaking.
Gelsight is the fundamental sensor to capture tactile information in this model. When facing a new object,we tilt and shake the object, and learns a physical embedding repsectively. Then the model fuse them into a joint physical feature embedding, which is used by a forward dynamics model to select the action that achieves the desired pose.

## Slide 09

A key component is the Gelsight sensor, playing a role like the hands of humans.
This sensor uses an internal camera to capture the deformation of a gel pad, providing detailed information about the contacted surface all at very high resolution—including normal and shear forces, as well as torques, which cannot be directly measured by traditional sensors. As shown in the graph, the captured images visually encode the shear forces and torques, which are visualized by displacements of markers as arrows. Unlike previous approaches, this work directly uses the raw information as input, that is, the displacement of the marks. This allows the model to learn and embed the gel’s dynamics and better interpret the physical information. Thus, it avoids the error in directly regressing the mechanical parameters caused by nonlinearity of the gel.

## Slide 10

The first part to interact is the tilting exploration actions. In this part, tilting will generate static patterns which embeds force and torque distribution. In this work we tilt the object at two angles: 20 degree and 45 degree. An intuition is that the smaller angle emphasizes parallel displacement, which reveals the mass of the object. The larger angle magnifies the effect of the torque, providing information about the center of mass. In this stage, stable contact provides clean, low-noise signals, making the measurements for mass and CoM more robust. Finally, we use a CNN and MLP network to extract the information from the input and returns an embedding representing information about mass and CoM.

## Slide 11

The second part---the shaking exploration actions utilize the information we get while carrying out simple dynamic process, which is useful for more complex dynamic manipulation tasks. In this stage, the input is a sequence of tactile frames captured during in-hand shaking, encoding information like friction and momentum of inertia: an intuitive observation is that the mark displacement intensity infers the moment of inertia, and the vibration patterns carry rich information about friction, as demonstrated by a simple analogy: the distinct features like tone and frequency of sound of scratching a blackboard versus sliding a wet finger over glass directly correlate with the frictional properties of the contact surface, just like the picture shows us. To learn the features in this stage, since time is involved, a per-frame CNN is used to extract the information from each frame, and then use LSTM to gather the information, returning an (80-dim) embedding encoding friction and momentum of inertia.

## Slide 12

With the information we gather in the two parts---the tilting embedding and the shaking embedding, a fusion network is used to concatenate and process these embeddings to produce a joint physical embedding, and use the joint embedding along with control parameters. to predict final swing angle.

## Slide 13

To increase the model generalization, the diversity of training constraints is significant. There are 3 major components: handle, rack, and weight, to change the mass, CoM, friction, and inertia of the system. The author collects a dataset of 33 modular objects built from combinations of these 3 components. To collect the training data, for each object the robot does about 50 swing-up trials, in total about 1650 trials, each consisting of exploration actions, action execution, and result recording.
For training, the authors adopted an end-to-end self-supervised learning approach.
The final swing-up angle serves as the supervision signal, and the loss function measures the prediction error between the model’s predicted angle and the actual measured result.
During inference, the robot samples a range of control parameters and selects the one whose predicted swing-up angle is closest to the desired target.

## Slide 16

This table highlights how our model disentangles physical features and learns distinct physical understanding from different actions.
Tilting is the expert in mass and center of mass, with very low error, as it directly measures gravitational torque.
Shaking is the friction expert, with over 90% accuracy, because it directly induces and senses slip.
Second, fusion creates the most robust model.
Our Combined method delivers the best performance on friction and moment of inertia, and remains highly competitive on all others. This synergy proves that fusion provides a more complete physical understanding than any single action.
Third, and most importantly, this knowledge is self-taught.
Our model was never directly trained on the true values of these physical properties. It learned these concepts unsupervised, purely by predicting the swing angle. This demonstrates the power and efficiency of our task-driven approach."

## Slide 17

PCA shows that object with similar dynamics cluster together in embedding space, , as shown in graph. This may allow fast policy transfer across objects with similar mechanical properties -the robot can infer good control parameters for new objects with similar embeddings.

## Slide 18

The main contributions of this work are the followings.
First, it’s the first approach that uses tactile-based physical embeddings for dynamic manipulation tasks.
Second, it avoids explicit physics modeling, making the method more generalizable and robust across different scenarios.

## Slide 20

There are still several limitations in our current approach.
First, the exploration actions are manually designed, such as tilting and shaking.
The robot does not yet learn how to explore objects by itself, which limits adaptability and prevents discovery of more efficient strategies.
Second, the method is too task-specific, since it is evaluated only on the swing-up manipulation.
It remains unclear whether the learned physical embeddings would generalize to other dynamic manipulation tasks like throwing or regrasping.
Third，The linear and rotational movements of the arm are predefined as well as the timing of gripper tightening. The robot only selects how much the gripper loosens at the impulse.
Also， the system shows a strong dependence on the specific hardware, including the robot arm and the GelSight tactile sensor.
Finally, there is a data limitation.
The dataset used for training is small and lacks diversity, which restricts the model’s ability to generalize to new or unseen objects.

## Slide 21

First, we can enable autonomous exploration.
Instead of relying on manually designed actions like tilting and shaking, the robot should learn how to explore by itself, selecting the optimal motions to understand an object’s physical properties.
Second, we aim to study cross-task transferability.
Currently, the embedding is trained only for the swing-up task.
Future work will test whether this learned tactile representation can be transferred to other manipulation tasks such as throwing or regrasping, which would demonstrate stronger generalization.
Third, we can develop better hardware.
We may develop a faster, low-latency tactile sensor and a more stable robotic arm.
Finally, expanding the dataset is essential.
A larger and more diverse dataset will make the learned embeddings more robust and capable of handling objects with unseen physical properties.
