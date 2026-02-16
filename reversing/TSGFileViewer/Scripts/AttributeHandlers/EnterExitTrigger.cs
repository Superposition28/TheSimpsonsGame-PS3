using Assets.Scripts;
using System.IO;
using UnityEditor;
using UnityEngine;
using static UnityEngine.GraphicsBuffer;

namespace AttributeHandlers
{
	public class EnterExitTrigger : AttributeHandler
	{
		public string m_enterTarget;
		public string m_exitTarget;
		public string m_insideTarget;
		public float m_insideTargetWait = 0.2f;
		public string m_activate;
		public string m_deactivate;
		public uint m_flags = 0;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_enterTarget = reader.ReadNullTerminatedString();
						break;

					case 1:
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_exitTarget = reader.ReadNullTerminatedString();
						break;

					case 2:
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_insideTarget = reader.ReadNullTerminatedString();
						break;

					case 3:
						m_insideTargetWait = attr.Data.ToSingleBigEndian();
						break;

					case 4:
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_activate = reader.ReadNullTerminatedString();
						break;

					case 5:
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_deactivate = reader.ReadNullTerminatedString();
						break;

					case 6:
						m_flags = attr.Data.ToUInt32BigEndian();
						break;
				}
			}
		}

		private void OnDrawGizmos()
		{
			Gizmos.color = new Color(0, 1, 1, 0.2f);

			Gizmos.matrix = Matrix4x4.TRS(transform.position, transform.rotation, transform.localScale);
			Gizmos.DrawWireCube(Vector3.zero, Vector3.one);
			Gizmos.DrawCube(Vector3.zero, Vector3.one);
			Gizmos.matrix = Matrix4x4.identity;

			Handles.Label(transform.position, $"ENTER: {m_enterTarget}\nEXIT: {m_enterTarget}\nINSIDE: {m_insideTarget}");
		}
	}
}
