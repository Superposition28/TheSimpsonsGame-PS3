using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class hkRigidBodyDeactivator : hkEntityDeactivator
	{
		public hkRigidBodyDeactivator()
		{
			Name = "hkRigidBodyDeactivator";
		}

		public override Mesh Deserialize(BinaryReader reader)
		{
			base.Deserialize(reader);
			return null;
		}
	}
}
