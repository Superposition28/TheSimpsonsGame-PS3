using Assets.Scripts;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using static UnityEngine.GraphicsBuffer;

namespace AttributeHandlers
{
	public class DUMMY : AttributeHandler
	{
		public string Name;
		public int nAttributes;

		public List<string> Attributes;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			Attributes = new List<string>(new string[nAttributes]);

			foreach (var attr in attrPacket.Attributes)
			{
				var data = attr.Data.ToInt32BigEndian();

				if (data < 0)
				{
					var str = "[!!INVALID!!]";
					try
					{
						reader.BaseStream.Position = attr.ReaderPosition + data; // negative offset
						str = reader.ReadNullTerminatedString();
					}
					catch {}

					Attributes[attr.Index] = $"{data:X8} ({str})";
				}
				else
				{
					Attributes[attr.Index] = $"{data:X8}";
				}
			}
		}

		/*private void OnDrawGizmos()
		{
			if (Name == "C8C5D222 (EnterExitTrigger)")
			{
				Gizmos.color = new Color(0, 1, 1, 0.1f);

				Gizmos.matrix = Matrix4x4.TRS(transform.position, transform.rotation, transform.localScale);
				Gizmos.DrawWireCube(Vector3.zero, Vector3.one);
				Gizmos.DrawCube(Vector3.zero, Vector3.one);
				Gizmos.matrix = Matrix4x4.identity;
			}
		}*/
	}
}
