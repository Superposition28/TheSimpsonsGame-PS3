using System.IO;
using Assets.Scripts;
using UnityEngine;

namespace AttributeHandlers
{
	public class MultiRemoveTarget : AttributeHandler
	{
		public const int MAX_REMOVE = 8;

		public string m_targetName;
		public Guid128[] m_arrEntityGuid = new Guid128[MAX_REMOVE];
		public uint m_options;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				if (attr.Index == 0)
				{
					reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
					m_targetName = reader.ReadNullTerminatedString();
				}
				else if (attr.Index == 9)
				{
					m_options = attr.Data.ToUInt32BigEndian();
				}
				else if (attr.Index <= MAX_REMOVE)
				{
					var idx = attr.Index - 1;

					reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
					m_arrEntityGuid[idx] = new Guid128(reader);
				}
			}
		}
	}
}
