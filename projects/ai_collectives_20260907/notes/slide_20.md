There are still several limitations in our current approach.
First, the exploration actions are manually designed, such as tilting and shaking.
The robot does not yet learn how to explore objects by itself, which limits adaptability and prevents discovery of more efficient strategies.
Second, the method is too task-specific, since it is evaluated only on the swing-up manipulation.
It remains unclear whether the learned physical embeddings would generalize to other dynamic manipulation tasks like throwing or regrasping.
Third，The linear and rotational movements of the arm are predefined as well as the timing of gripper tightening. The robot only selects how much the gripper loosens at the impulse.
Also， the system shows a strong dependence on the specific hardware, including the robot arm and the GelSight tactile sensor.
Finally, there is a data limitation.
The dataset used for training is small and lacks diversity, which restricts the model’s ability to generalize to new or unseen objects.
