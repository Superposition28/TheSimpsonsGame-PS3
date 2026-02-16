using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class TriggerBox : AttributeHandler
	{
		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			
		}

		private void OnDrawGizmos()
		{
			Gizmos.matrix = Matrix4x4.TRS(transform.position, transform.rotation, transform.localScale);
			Gizmos.DrawWireCube(Vector3.zero, Vector3.one);
			Gizmos.matrix = Matrix4x4.identity;
		}
	}
}
