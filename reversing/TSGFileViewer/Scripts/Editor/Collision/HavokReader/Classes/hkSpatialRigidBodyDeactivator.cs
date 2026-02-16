using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class hkSpatialRigidBodyDeactivator : hkRigidBodyDeactivator
	{
		public hkSpatialRigidBodyDeactivator()
		{
			Name = "hkSpatialRigidBodyDeactivator";
		}

		public Sample HighFrequencySample;
		public Sample LowFrequencySample;
		public float RadiusSquared;
		public float MinHighFrequencyTranslation;
		public float MinHighFrequencyRotation;
		public float MinLowFrequencyTranslation;
		public float MinLowFrequencyRotation;

		public override Mesh Deserialize(BinaryReader reader)
		{
			base.Deserialize(reader);

			reader.Align(16);

			HighFrequencySample = new()
			{
				Position = reader.ReadVector4BigEndian(),
				Rotation = reader.ReadQuaternionBigEndian()
			};

			LowFrequencySample = new()
			{
				Position = reader.ReadVector4BigEndian(),
				Rotation = reader.ReadQuaternionBigEndian()
			};

			RadiusSquared = reader.ReadSingleBigEndian();
			MinHighFrequencyTranslation = reader.ReadSingleBigEndian();
			MinHighFrequencyRotation = reader.ReadSingleBigEndian();
			MinLowFrequencyTranslation = reader.ReadSingleBigEndian();
			MinLowFrequencyRotation = reader.ReadSingleBigEndian();
			return null;
		}
	}

	public class Sample
	{
		public Vector4 Position;
		public Quaternion Rotation;
	}
}
