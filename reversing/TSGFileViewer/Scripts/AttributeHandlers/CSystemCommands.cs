using System;
using System.IO;
using Assets.Scripts;
using UnityEngine;

namespace AttributeHandlers
{
	public class CSystemCommands : AttributeHandler
	{
		public int unk_0;
		public RwMatrixTag m_matrix;
		public int unk_2;
		public int unk_3;
		public int unk_4;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
						unk_0 = attr.Data.ToInt32BigEndian();
						break;

					case 1:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_matrix = new RwMatrixTag(reader);
						break;
					}

					case 2:
						unk_2 = attr.Data.ToInt32BigEndian();
						break;

					case 3:
						unk_3 = attr.Data.ToInt32BigEndian();
						break;

					case 4:
						unk_4 = attr.Data.ToInt32BigEndian();
						break;

					default:
						throw new NotImplementedException();
				}
			}
		}

		private void OnDrawGizmos()
		{
			if (GetComponent<TriggerBase>() == null)
			{
				Gizmos.DrawWireSphere(transform.position, 0.5f);
			}
		}
	}
}
