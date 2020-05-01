#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 24 15:48:52 2020
@author: Jesse Haviland
"""

import numpy as np
import spatialmath.base as sp
from roboticstoolbox.robot.ET import ET


class ETS(object):
    """
    The Elementary Transform Sequence (ETS). A superclass which represents the
    kinematics of a serial-link manipulator

    :param et_list: List of elementary transforms which represent the robot
        kinematics
    :type et_list: list of etb.robot.et
    :param q_idx: List of indexes within the ets_list which correspond to
        joints
    :type q_idx: list of int
    :param name: Name of the robot
    :type name: str, optional
    :param manufacturer: Manufacturer of the robot
    :type manufacturer: str, optional
    :param base: Location of the base is the world frame
    :type base: float np.ndarray(4,4), optional
    :param tool: Offset of the flange of the robot to the end-effector
    :type tool: float np.ndarray(4,4), optional

    References: Kinematic Derivatives using the Elementary Transform Sequence,
        J. Haviland and P. Corke
    """

    def __init__(
            self,
            et_list,
            q_idx,
            name='noname',
            manufacturer='',
            base=np.eye(4, 4),
            tool=np.eye(4, 4)
            ):

        self._name = name
        self._manuf = manufacturer
        self._ets = et_list
        self._q_idx = q_idx
        self._base = base
        self._tool = tool
        self._T = np.eye(4)

        super(ETS, self).__init__()

        # Number of transforms in the ETS
        self._M = len(self._ets)

        # Number of joints in the robot
        self._n = len(self._q_idx)

        # Current joint angles of the robot
        self._q = np.zeros((self._n,))

    @classmethod
    def dh_to_ets(cls, robot):
        """
        Converts a robot modelled with standard or modified DH parameters to an
        ETS representation

        :param robot: The robot model to be converted
        :type robot: SerialLink
        :return: List of returned :class:`bluepy.btle.Characteristic` objects
        :rtype: ets class
        """
        ets = []
        q_idx = []
        M = 0

        for j in range(robot.n):
            L = robot.links[j]

            # Method for modified DH parameters
            if robot.mdh:

                # Append Tx(a)
                if L.a != 0:
                    ets.append(et(et.Ttx, L.a))
                    M += 1

                # Append Rx(alpha)
                if L.alpha != 0:
                    ets.append(et(et.TRx, L.alpha))
                    M += 1

                if L.is_revolute:
                    # Append Tz(d)
                    if L.d != 0:
                        ets.append(et(et.Ttz, L.d))
                        M += 1

                    # Append Rz(q)
                    ets.append(et(et.TRz, i=j+1))
                    q_idx.append(M)
                    M += 1

                else:
                    # Append Tz(q)
                    ets.append(et(et.Ttz, i=j+1))
                    q_idx.append(M)
                    M += 1

                    # Append Rz(theta)
                    if L.theta != 0:
                        ets.append(et(et.TRz, L.alpha))
                        M += 1

        return cls(
            ets,
            q_idx,
            robot.name,
            robot.manuf,
            robot.base,
            robot.tool)

    @property
    def q(self):
        return self._q

    @property
    def name(self):
        return self._name

    @property
    def manuf(self):
        return self._manuf

    @property
    def base(self):
        return self._base

    @property
    def tool(self):
        return self._tool

    @property
    def n(self):
        return self._n

    @property
    def M(self):
        return self._M

    @property
    def ets(self):
        return self._ets

    @property
    def q_idx(self):
        return self._q_idx

    def fkine(self, q):
        '''
        Evaluates the forward kinematics of a robot based on its ETS and
        joint angles q.

        :param q: The joint coordinates of the robot
        :type q: float np.ndarray(n,)
        :return: The transformation matrix representing the pose of the
            end-effector
        :rtype: float np.ndarray(4,4)

        References: Kinematic Derivatives using the Elementary Transform
            Sequence, J. Haviland and P. Corke
        '''

        # if not isinstance(q, np.ndarray):
        #     raise TypeError('q array must be a numpy ndarray.')
        # if q.shape != (self._n,):
        #     raise ValueError('q must be a 1 dim (n,) array')

        j = 0
        trans = np.eye(4)

        for i in range(self.M):
            if self._ets[i]._type == 1:
                T = self._ets[i].T(q[j])
                j += 1
            else:
                T = self._ets[i].T()

            trans = trans @ T

        trans = trans @ self.tool

        return trans

    def jacob0(self, q):
        """
        The manipulator Jacobian matrix maps joint velocity to end-effector
        spatial velocity, expressed in the world-coordinate frame.

        :param q: The joint coordinates of the robot
        :type q: float np.ndarray(n,)
        :return: The manipulator Jacobian in 0 frame
        :rtype: float np.ndarray(6,n)

        References: Kinematic Derivatives using the Elementary Transform
            Sequence, J. Haviland and P. Corke
        """
        T = self.fkine(q)
        U = np.eye(4)
        j = 0
        J = np.zeros((6, self.n))

        for i in range(self.M):

            if i != self.q_idx[j]:
                U = U @ self.ets[i].T()
            else:
                if self.ets[i].axis_func == ET.TRz:
                    U = U @ self.ets[i].T(q[j])
                    Tu = np.linalg.inv(U) @ T

                    n = U[:3, 0]
                    o = U[:3, 1]
                    a = U[:3, 2]
                    y = Tu[1, 3]
                    x = Tu[0, 3]

                    J[:3, j] = (o * x) - (n * y)
                    J[3:, j] = a

                    j += 1

        return J

    def hessian0(self, q, J=None):
        """
        The manipulator Hessian tensor maps joint acceleration to end-effector
        spatial acceleration, expressed in the world-coordinate frame. This
        function calulcates this based on the ETS of the robot.

        :param q: The joint coordinates of the robot
        :type q: float np.ndarray(n,)
        :return: The manipulator Hessian in 0 frame
        :rtype: float np.ndarray(6,n,n)

        References: Kinematic Derivatives using the Elementary Transform
            Sequence, J. Haviland and P. Corke
        """
        if J is None:
            J = self.jacob0(q)

        H = np.zeros((6, self.n, self.n))

        for j in range(self.n):
            for i in range(j, self.n):

                H[:3, i, j] = np.cross(J[3:, j], J[:3, i])
                H[3:, i, j] = np.cross(J[3:, j], J[3:, i])

                if i != j:
                    H[:3, j, i] = H[:3, i, j]

        return H

    def manipulability(self, q, J=None):
        """
        Calculates the manipulability index (scalar) robot at the joint
        configuration q. It indicates dexterity, that is, how isotropic the
        robot's motion is with respect to the 6 degrees of Cartesian motion.
        The measure is high when the manipulator is capable of equal motion
        in all directions and low when the manipulator is close to a
        singularity.

        :param q: The joint coordinates of the robot
        :type q: float np.ndarray(n,)
        :return: The manipulability index
        :rtype: float

        References: Analysis and control of robot manipulators with redundancy,
        T. Yoshikawa,
        Robotics Research: The First International Symposium (M. Brady and
        R. Paul, eds.), pp. 735-747, The MIT press, 1984.
        """

        if J is None:
            J = self.jacob0(q)

        return np.sqrt(np.linalg.det(J @ np.transpose(J)))

    def jacobm(self, q, J=None, H=None, manipulability=None):
        """
        Calculates the manipulability Jacobian. This measure relates the rate
        of change of the manipulability to the joint velocities of the robot.

        :param q: The joint coordinates of the robot
        :type q: float np.ndarray(n,)
        :return: The manipulability Jacobian
        :rtype: float np.ndarray(n,1)

        References: Maximising Manipulability in Resolved-Rate Motion Control,
            J. Haviland and P. Corke
        """

        if manipulability is None:
            manipulability = self.manipulability(q)

        if J is None:
            J = self.jacob0(q)

        if H is None:
            H = self.hessian0(q)

        b = np.linalg.inv(J @ np.transpose(J))
        Jm = np.zeros((self.n, 1))

        for i in range(self.n):
            c = J @ np.transpose(H[:, :, i])
            Jm[i, 0] = manipulability * \
                np.transpose(c.flatten('F')) @ b.flatten('F')

        return Jm

    def __str__(self):
        """
        Pretty prints the ETS Model of the robot. Will output angles in degrees

        :return: Pretty print of the robot model
        :rtype: str
        """
        axes = ''

        for i in range(self._n):
            axes += self.ets[self.q_idx[i]].axis

        rpy = sp.tr2rpy(self.tool, unit='deg')

        if rpy[0] == 0:
            rpy[0] = 0

        if rpy[1] == 0:
            rpy[1] = 0

        if rpy[2] == 0:
            rpy[2] = 0

        model = '\n%s (%s): %d axis, %s, ETS\n'\
            'Elementary Transform Sequence:\n'\
            '%s\n'\
            'tool:  t = (%g, %g, %g),  RPY/xyz = (%g, %g, %g) deg' % (
                self.name, self.manuf, self.n, axes,
                self.ets,
                self.tool[0, 3], self.tool[1, 3],
                self.tool[2, 3], rpy[0], rpy[1], rpy[2]
            )

        return model
