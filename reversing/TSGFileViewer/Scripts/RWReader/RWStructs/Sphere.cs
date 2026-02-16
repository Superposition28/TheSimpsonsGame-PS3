using System;

namespace RWReader.RWStructs
{
	[Serializable]
	public struct Sphere
	{
		public float X;
		public float Y;
		public float Z;
		public float Radius;

		public Sphere(float x, float y, float z, float radius)
		{
			X = x;
			Y = y;
			Z = z;
			Radius = radius;
		}
	}
}