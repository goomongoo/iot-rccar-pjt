/*
 * motorhat.h
 *
 *  Created on: Dec 3, 2025
 *      Author: mongoo
 */

#ifndef INC_MOTORHAT_H_
#define INC_MOTORHAT_H_

#include "main.h"

void MotorHat_Init(void);
void Motor_SetSteer(int16_t angle);
void Motor_SetThrottle(int16_t speed);

#endif /* INC_MOTORHAT_H_ */
