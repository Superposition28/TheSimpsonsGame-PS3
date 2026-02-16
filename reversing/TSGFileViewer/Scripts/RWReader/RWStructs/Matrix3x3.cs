using System;
using System.Numerics;

namespace RWReader.RWStructs
{
	public struct Matrix3x3
	{
		public Vector3 Right;
		public Vector3 Up;
		public Vector3 At;

		public Matrix3x3(Vector3 right, Vector3 up, Vector3 at)
		{
			Right = right;
			Up = up;
			At = at;
		}
	}
}
