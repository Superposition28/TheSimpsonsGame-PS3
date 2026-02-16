using System.IO;
using Assets.Scripts;
using UnityEngine;

namespace AttributeHandlers
{
	public class TestEntityExists : AttributeHandler
	{
		public string m_targetName;
		public Guid128 m_queryEntityGuid;
		public string m_existTarget;
		public string m_noExistTarget;

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
						m_queryEntityGuid = new Guid128(reader);
						break;
					}

					case 2:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_existTarget = reader.ReadNullTerminatedString();
							break;
					}

					case 3:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_noExistTarget = reader.ReadNullTerminatedString();
							break;
					}
				}
			}
		}
	}
}
