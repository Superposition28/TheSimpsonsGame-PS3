using System;
using System.Numerics;

namespace RWReader.RWStructs
{
	public struct Frame
	{
		public Matrix3x3 RotationMatrix;
		public Vector3 Position;
		public int ParentFrame;
		public int MatrixFlags;
	}
}