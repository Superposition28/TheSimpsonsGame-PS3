using System;
using Assets.Scripts;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace AttributeHandlers
{
	public class TriggerBase : AttributeHandler
	{
		public string m_targetName;
		public string m_activate;
		public string m_deactivate;
		public int m_primitive;
		public string m_target;
		public float m_delay;
		public int m_count = -1;
		public string m_reverseTarget;
		public uint m_options;
		// touch record?
		public float m_wait;
		public float m_speedSquared;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
						{
							reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
							m_targetName = reader.ReadNullTerminatedString();
							break;
						}

					case 1:
						{
							reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
							m_activate = reader.ReadNullTerminatedString();
							break;
						}

					case 2:
						{
							reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
							m_deactivate = reader.ReadNullTerminatedString();
							break;
						}

					case 3:
						{
							m_primitive = attr.Data.ToInt32BigEndian();
							break;
						}

					case 4:
						{
							reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
							m_target = reader.ReadNullTerminatedString();
							break;
						}

					case 5:
						{
							m_delay = attr.Data.ToSingleBigEndian();
							break;
						}

					case 6:
						{
							m_count = attr.Data.ToInt32BigEndian();
							break;
						}

					case 7:
						{
							reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
							m_reverseTarget = reader.ReadNullTerminatedString();
							break;
						}

					case 8:
					{
						m_options = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 0xA:
						{
							m_wait = attr.Data.ToSingleBigEndian();
							break;
						}

					case 0xB:
						{
							// yes, this magic number is used in renderware
							// close to miles/h -> metres/s conversion (0.44704) ??? no idea
							m_speedSquared = attr.Data.ToSingleBigEndian() * 0.44715446f;
							m_speedSquared *= m_speedSquared;
							break;
						}
				}
			}
		}

		private void OnDrawGizmos()
		{
			Gizmos.color = new Color(0, 1, 0, 0.2f);

			Gizmos.matrix = Matrix4x4.TRS(transform.position, transform.rotation, transform.localScale);
			Gizmos.DrawWireCube(Vector3.zero, Vector3.one);
			Gizmos.DrawCube(Vector3.zero, Vector3.one);
			Gizmos.matrix = Matrix4x4.identity;

			Handles.Label(transform.position, m_target);
		}
	}
}
