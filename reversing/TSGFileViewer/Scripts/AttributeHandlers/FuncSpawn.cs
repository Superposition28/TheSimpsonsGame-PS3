using Assets.Scripts;
using System;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class FuncSpawn : AttributeHandler
	{
		public Guid128 m_spawnTarget;
		public string m_targetName;
		public string m_entityCreated;
		// m_rotation
		// m_position
		public uint m_funcSpawnFlags;

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
						m_entityCreated = reader.ReadNullTerminatedString();
						break;
					}

					case 2:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_spawnTarget = new Guid128(reader);
						break;
					}

					case 3:
					{
						m_funcSpawnFlags = attr.Data.ToUInt32BigEndian();
						break;
					}

					default:
						throw new NotImplementedException();
				}
			}
		}
	}
}
